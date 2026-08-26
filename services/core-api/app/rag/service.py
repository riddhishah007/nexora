"""Blueprint §13 + §16: ingest (parse -> chunk -> embed -> store) and
retrieval (embed query -> pgvector similarity + Phase 28 hybrid/rerank) — always scoped by user_id.
"""

import re
import uuid

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.llm.gateway import LLMGateway
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.rag.chunker import chunk_text
from app.tools.pdf_io import document_path, load_owned_document, read_pdf_pages

_TOKEN_RE = re.compile(r"[A-Za-z0-9]{2,}")
_STOP = frozenset(
    {
        "the",
        "and",
        "for",
        "are",
        "but",
        "not",
        "you",
        "all",
        "can",
        "had",
        "her",
        "was",
        "one",
        "our",
        "out",
        "has",
        "have",
        "with",
        "this",
        "that",
        "from",
        "they",
        "will",
        "would",
        "there",
        "their",
    }
)


def _tokenize(text: str) -> list[str]:
    toks = [t.lower() for t in _TOKEN_RE.findall(text or "")]
    return [t for t in toks if t not in _STOP][:32]


def _keyword_score(query_tokens: list[str], content: str) -> float:
    """Lightweight BM25-ish keyword score in [0,1].

    - Exact token overlap / query length, with a small length-normalization bonus
      so that a 2-token query hitting both tokens scores 1.0.
    - Never raises.
    """
    if not query_tokens:
        return 0.0
    try:
        content_l = content.lower()
        # fast set overlap first
        content_tokens = set(_TOKEN_RE.findall(content_l))
        hits = sum(1 for t in query_tokens if t in content_tokens)
        # sub-string hits for compound tokens (e.g. "HTTP3" vs "HTTP/3")
        if hits == 0:
            hits = sum(1 for t in query_tokens if t in content_l)
        return min(1.0, hits / len(query_tokens))
    except Exception:
        return 0.0


async def _maybe_rewrite_query(query: str, gateway: LLMGateway) -> str:
    """Phase 28: optional LLM query rewrite (off by default).

    Expands a short user query into a retrieval-friendly form. If the
    gateway is mock or the call fails, returns the original query verbatim.
    """
    if not settings.rag_query_rewrite_enabled:
        return query
    if len(query.strip().split()) >= 12:
        return query  # long queries are already specific
    try:
        from app.llm.schemas import ModelTier

        prompt = (
            "Rewrite the following question into a concise, keyword-rich search query "
            "for a vector database. Output ONLY the rewritten query, no explanation.\n\n"
            f"Question: {query}\nRewritten:"
        )
        resp = await gateway.generate(prompt=prompt, tier=ModelTier.LITE)
        rewritten = (resp.text or "").strip().split("\n")[0].strip()[:400]
        # Guard: if model hallucinated a long paragraph, keep original
        if len(rewritten) < 4 or len(rewritten) > 300:
            return query
        # Must contain at least one token from original
        q_toks = set(_tokenize(query))
        r_toks = set(_tokenize(rewritten))
        if q_toks and not (q_toks & r_toks):
            return query
        return rewritten
    except Exception:
        return query


async def ingest_document(
    document_id: str,
    db: AsyncSession,
    gateway: LLMGateway,
    user_id: str,
) -> dict:
    """Chunk + embed a user-owned PDF and replace its chunks idempotently.

    Returns dict with {chunks, chars, page_count} or raises ValueError that
    the caller maps to 404/500 (§16 isolation).
    """
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError as exc:
        raise ValueError("Invalid document_id") from exc

    doc_row = await db.get(Document, doc_uuid)
    if doc_row is None or str(doc_row.user_id) != user_id:
        raise ValueError("Document not found")
    storage = document_path(doc_row)
    if not storage.is_file():
        raise ValueError("File missing from storage")

    page_count, pages = read_pdf_pages(storage)
    full_text = "\n\n".join(p.strip() for p in pages if p.strip())
    # Also include filename hint so file-name-only PDFs still have content
    if not full_text.strip():
        raise ValueError("This PDF contains no extractable text")

    chunks = chunk_text(full_text)
    if not chunks:
        raise ValueError("No chunks produced from document")

    # Idempotent replace: remove previous chunks for this document
    await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc_uuid))

    # Batch embed
    batch = settings.rag_embed_batch
    all_vectors: list[list[float]] = []
    for i in range(0, len(chunks), batch):
        batch_texts = chunks[i: i + batch]
        vectors = await gateway.embed(batch_texts)
        all_vectors.extend(vectors)

    now_chunks: list[DocumentChunk] = []
    for idx, (text, emb) in enumerate(zip(chunks, all_vectors)):
        now_chunks.append(
            DocumentChunk(
                document_id=doc_uuid,
                user_id=doc_row.user_id,
                chunk_index=idx,
                content=text,
                embedding=emb,
            )
        )
        db.add(now_chunks[-1])

    # Also persist page_count if we extracted pages
    if page_count is not None and doc_row.page_count is None:
        doc_row.page_count = page_count

    await db.commit()

    return {
        "document_id": document_id,
        "chunks": len(now_chunks),
        "chars": len(full_text),
        "page_count": page_count,
    }



async def retrieve(
    query: str,
    db: AsyncSession,
    gateway: LLMGateway,
    user_id: str,
    top_k: int | None = None,
    document_id: str | None = None,
) -> list[dict]:
    """Hybrid vector + keyword retrieval with rerank (§13 V1 + §16).

    Steps:
    1. Optional query rewrite (LLM, off by default).
    2. Vector candidates: cosine distance, over-fetched (top_k * multiplier, capped at 20).
    3. Keyword candidates: ILIKE per token, user/document scoped.
    4. Union + rerank via weighted sum (alpha * vector_score + (1-alpha) * keyword_score).
    5. Return top_k by combined score, preserving the original distance + a
       `score` field for debugging (higher is better).

    Every SQL query is filtered by user_id (or document_id) at the query
    layer — never in Python after the fact (§16).
    """
    top_k = top_k or settings.rag_top_k
    top_k = max(1, min(top_k, 20))

    if not query.strip():
        return []

    query = query.strip()[:4000]
    # Phase 28: optional expansion before embedding
    query_for_embed = await _maybe_rewrite_query(query, gateway)

    doc_filter_uuid: uuid.UUID | None = None
    if document_id:
        try:
            doc_filter_uuid = uuid.UUID(document_id)
        except ValueError as exc:
            raise ValueError("Invalid document_id") from exc
        doc = await db.get(Document, doc_filter_uuid)
        if doc is None or str(doc.user_id) != user_id:
            raise ValueError("Document not found")

    tokens = _tokenize(query)
    query_vec = (await gateway.embed([query_for_embed]))[0]

    user_uuid = uuid.UUID(user_id)
    # Over-fetch vector candidates so rerank has headroom
    fetch_k = max(top_k, min(20, top_k * max(1, settings.rag_candidate_multiplier)))
    v_stmt = (
        select(
            DocumentChunk,
            DocumentChunk.embedding.cosine_distance(query_vec).label("distance"),
        )
        .where(DocumentChunk.user_id == user_uuid)
        .order_by(DocumentChunk.embedding.cosine_distance(query_vec))
        .limit(fetch_k)
    )
    if doc_filter_uuid is not None:
        v_stmt = v_stmt.where(DocumentChunk.document_id == doc_filter_uuid)

    v_rows = (await db.execute(v_stmt)).all()

    # Keyword candidates (ILIKE per token, cheap — no tsvector migration required).
    # Fetch at most 10 keyword hits to bound I/O; union with vector candidates.
    kw_chunks: list[tuple[DocumentChunk, float]] = []
    if tokens and settings.rag_rerank_enabled:
        # Use OR of ILIKEs; still scoped by user_id/document_id.
        ilike_clauses = [DocumentChunk.content.ilike(f"%{t}%") for t in tokens[:8]]
        k_stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.user_id == user_uuid)
            .where(or_(*ilike_clauses))
            .limit(10)
        )
        if doc_filter_uuid is not None:
            k_stmt = k_stmt.where(DocumentChunk.document_id == doc_filter_uuid)
        try:
            for row in (await db.execute(k_stmt)).scalars().all():
                # Avoid double-counting vectors we already have; store with pseudo-distance
                kw_chunks.append((row, 1.0))
        except Exception:
            kw_chunks = []

    # Union by chunk id
    seen: dict[str, tuple[DocumentChunk, float]] = {}
    for chunk, dist in v_rows:
        seen[str(chunk.id)] = (chunk, float(dist) if dist is not None else 0.0)
    for chunk, pseudo_dist in kw_chunks:
        cid = str(chunk.id)
        if cid not in seen:
            seen[cid] = (chunk, pseudo_dist)

    if not seen:
        return []

    # Rerank
    alpha = float(settings.rag_hybrid_alpha) if settings.rag_rerank_enabled else 1.0
    alpha = max(0.0, min(1.0, alpha))

    scored: list[tuple[float, DocumentChunk, float]] = []
    for chunk, distance in seen.values():
        vec_score = max(0.0, 1.0 - float(distance))  # cosine distance in [0,2]; 1-dist ~ similarity
        kw_score = _keyword_score(tokens, chunk.content) if settings.rag_rerank_enabled else 0.0
        combined = alpha * vec_score + (1.0 - alpha) * kw_score
        scored.append((combined, chunk, float(distance)))

    scored.sort(key=lambda x: x[0], reverse=True)

    out: list[dict] = []
    for combined, chunk, distance in scored[:top_k]:
        out.append(
            {
                "chunk_id": str(chunk.id),
                "document_id": str(chunk.document_id),
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "distance": float(distance),
                "score": round(float(combined), 4),
            }
        )
    return out
