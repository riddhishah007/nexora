"""Phase 12 — RAG endpoints (§13, §16 isolation) + Phase 16 queue.

POST /api/v1/rag/ingest  — async enqueue (default) or sync with ?sync=true
GET  /api/v1/rag/jobs/{job_id} — poll background ingest job
POST /api/v1/rag/query   — grounded Q&A over ingested chunks
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import AGENT_REGISTRY, rag_agent
from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.llm import get_llm_gateway
from app.llm.gateway import LLMGateway
from app.models.job import JOB_TYPE_RAG_INGEST, Job
from app.models.user import User
from app.rag.service import ingest_document
from app.queue.bus import enqueue

router = APIRouter(prefix="/rag", tags=["rag"])


class RagIngestRequest(BaseModel):
    document_id: str = Field(min_length=32, max_length=64)


class RagIngestResponse(BaseModel):
    document_id: str
    chunks: int
    chars: int
    page_count: int | None


class RagIngestJobResponse(BaseModel):
    job_id: str
    document_id: str
    status: str
    idempotency_key: str | None = None


class RagQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    document_id: str | None = Field(default=None, min_length=32, max_length=64)


class RagCitation(BaseModel):
    chunk_id: str
    document_id: str
    chunk_index: int
    content: str
    distance: float


class RagQueryResponse(BaseModel):
    query: str
    answer: str
    citations: list[RagCitation]
    provider: str
    model: str
    latency_ms: int
    mock: bool


@router.post("/ingest", response_model=RagIngestJobResponse | RagIngestResponse)
async def rag_ingest(
    payload: RagIngestRequest,
    sync: bool = Query(default=False, description="If true, run ingest synchronously (no queue)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Ownership check early (404 if not yours)
    from sqlalchemy import select as _select
    from app.models.document import Document as _Doc
    import uuid as _uuid

    try:
        doc_uuid = _uuid.UUID(payload.document_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found") from None
    doc = await db.get(_Doc, doc_uuid)
    if doc is None or str(doc.user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if sync:
        gateway = get_llm_gateway()
        try:
            result = await ingest_document(
                document_id=payload.document_id, db=db, gateway=gateway, user_id=str(current_user.id)
            )
        except ValueError as exc:
            msg = str(exc)
            if "not found" in msg.lower() or "missing" in msg.lower() or "invalid" in msg.lower():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from None
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from None
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)[:300]) from exc
        return RagIngestResponse(**result)

    # async: enqueue for worker (§18)
    idem = f"rag_ingest:{current_user.id}:{payload.document_id}"
    job = await enqueue(
        db, current_user.id, JOB_TYPE_RAG_INGEST,
        payload={"document_id": payload.document_id},
        idempotency_key=idem,
    )
    return RagIngestJobResponse(job_id=str(job.id), document_id=payload.document_id, status=job.status, idempotency_key=idem)


@router.get("/jobs/{job_id}")
async def rag_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import uuid as _uuid
    from sqlalchemy import select as _select

    try:
        jid = _uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found") from None
    job = await db.get(Job, jid)
    if job is None or str(job.user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return {
        "job_id": str(job.id),
        "type": job.type,
        "status": job.status,
        "payload": job.payload,
        "result": job.result,
        "error": job.error,
        "attempts": job.attempts,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


@router.post("/query", response_model=RagQueryResponse)
async def rag_query(
    payload: RagQueryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RagQueryResponse:
    if "rag-agent" not in AGENT_REGISTRY:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="RAG agent unavailable")

    top_k = payload.top_k or settings.rag_top_k

    answer, citations_raw, llm = await rag_agent.run(
        query=payload.query,
        db=db,
        user_id=str(current_user.id),
        top_k=top_k,
        document_id=payload.document_id,
    )

    # Document-scoped 404 surfacing
    if llm.provider == "none" and not citations_raw and ("not found" in answer.lower() if answer else False):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=answer)

    await LLMGateway.record_usage(db, current_user.id, llm)

    citations = [
        RagCitation(
            chunk_id=c.get("chunk_id", ""),
            document_id=c.get("document_id", ""),
            chunk_index=c.get("chunk_index", 0),
            content=c.get("content", "")[:1200],
            distance=float(c.get("distance", 0)),
        )
        for c in citations_raw
    ]

    return RagQueryResponse(
        query=payload.query,
        answer=answer,
        citations=citations,
        provider=llm.provider,
        model=llm.model,
        latency_ms=llm.latency_ms,
        mock=llm.mock,
    )
