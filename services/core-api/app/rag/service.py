"""Blueprint §13 + §16: ingest (parse -> chunk -> embed -> store) and
retrieval (embed query -> pgvector similarity) — always scoped by user_id.
"""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.llm.gateway import LLMGateway
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.rag.chunker import chunk_text
from app.tools.pdf_io import document_path, load_owned_document, read_pdf_pages


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
    """Vector search — every query is filtered by user_id (§16).

    Optionally narrowed to a single document. Returns list of
    {chunk_id, document_id, chunk_index, content, distance}.
    """
    top_k = top_k or settings.rag_top_k
    top_k = max(1, min(top_k, 20))

    if not query.strip():
        return []

    # Clamp query length to avoid insane embed calls
    query = query.strip()[:4000]

    doc_filter_uuid: uuid.UUID | None = None
    if document_id:
        try:
            doc_filter_uuid = uuid.UUID(document_id)
        except ValueError as exc:
            raise ValueError("Invalid document_id") from exc
        # Ownership check for document-scoped search — never leak existence
        doc = await db.get(Document, doc_filter_uuid)
        if doc is None or str(doc.user_id) != user_id:
            raise ValueError("Document not found")

    query_vec = (await gateway.embed([query]))[0]

    # pgvector cosine distance: embedding <=> query. Using l2/cosine; <=> is cosine.
    # SQL: SELECT * FROM document_chunks WHERE user_id=:uid ORDER BY embedding <=> :q LIMIT :k
    user_uuid = uuid.UUID(user_id)
    stmt = (
        select(
            DocumentChunk,
            DocumentChunk.embedding.cosine_distance(query_vec).label("distance"),
        )
        .where(DocumentChunk.user_id == user_uuid)
        .order_by(DocumentChunk.embedding.cosine_distance(query_vec))
        .limit(top_k)
    )
    if doc_filter_uuid is not None:
        stmt = stmt.where(DocumentChunk.document_id == doc_filter_uuid)

    result = await db.execute(stmt)
    rows = result.all()

    out: list[dict] = []
    for chunk, distance in rows:
        out.append(
            {
                "chunk_id": str(chunk.id),
                "document_id": str(chunk.document_id),
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "distance": float(distance) if distance is not None else 0.0,
            }
        )
    return out
