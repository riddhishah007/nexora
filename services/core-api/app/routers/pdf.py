from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import AGENT_REGISTRY, pdf_agent
from app.database import get_db
from app.dependencies import get_current_user
from app.llm.gateway import LLMGateway
from app.models.user import User

router = APIRouter(prefix="/pdf", tags=["pdf"])


class PdfSummarizeRequest(BaseModel):
    document_id: str = Field(min_length=32, max_length=64)


class PdfSummarizeResponse(BaseModel):
    document_id: str
    answer: str
    page_count: int | None
    truncated: bool
    chars: int
    provider: str
    model: str
    latency_ms: int
    mock: bool


@router.post("/summarize", response_model=PdfSummarizeResponse)
async def summarize_pdf(
    payload: PdfSummarizeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PdfSummarizeResponse:
    if "pdf-agent" not in AGENT_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PDF agent unavailable",
        )

    answer, meta, llm = await pdf_agent.run(
        payload.document_id, db, user_id=str(current_user.id)
    )

    if llm.provider == "none" and meta.get("chars", 0) == 0 and (
        "not found" in answer or "missing" in answer or "invalid" in answer
    ):
        # Isolation: unreadable/foreign documents surface as 404.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=answer,
        )
    await LLMGateway.record_usage(db, current_user.id, llm)

    return PdfSummarizeResponse(
        document_id=payload.document_id,
        answer=answer,
        page_count=meta.get("page_count"),
        truncated=meta.get("truncated", False),
        chars=meta.get("chars", 0),
        provider=llm.provider,
        model=llm.model,
        latency_ms=llm.latency_ms,
        mock=llm.mock,
    )
