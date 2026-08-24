"""Phase 12 — RAG endpoints (§13, §16 isolation).

POST /api/v1/rag/ingest  — chunk + embed one of the caller's PDFs
POST /api/v1/rag/query   — grounded Q&A over ingested chunks
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import AGENT_REGISTRY, rag_agent
from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.llm import get_llm_gateway
from app.llm.gateway import LLMGateway
from app.models.user import User
from app.rag.service import ingest_document

router = APIRouter(prefix="/rag", tags=["rag"])


class RagIngestRequest(BaseModel):
    document_id: str = Field(min_length=32, max_length=64)


class RagIngestResponse(BaseModel):
    document_id: str
    chunks: int
    chars: int
    page_count: int | None


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


@router.post("/ingest", response_model=RagIngestResponse)
async def rag_ingest(
    payload: RagIngestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RagIngestResponse:
    gateway = get_llm_gateway()
    # Use configured batch size — pass through here for observability

    try:
        result = await ingest_document(
            document_id=payload.document_id,
            db=db,
            gateway=gateway,
            user_id=str(current_user.id),
        )
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower() or "missing" in msg.lower() or "invalid" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from None
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from None
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)[:300]) from exc

    return RagIngestResponse(**result)


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
