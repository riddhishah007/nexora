from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.llm import GenerateRequest, GenerateResponse, get_llm_gateway
from app.llm.gateway import LLMGateway
from app.models.user import User

router = APIRouter(prefix="/llm", tags=["llm"])


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    payload: GenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    gateway: LLMGateway = Depends(get_llm_gateway),
) -> GenerateResponse:
    try:
        response = await gateway.generate(
            prompt=payload.prompt,
            tier=payload.tier,
            system=payload.system,
        )
    except TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="LLM provider timed out",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM provider error: {exc}",
        )

    await LLMGateway.record_usage(db, current_user.id, response)
    return GenerateResponse(
        text=response.text,
        provider=response.provider,
        model=response.model,
        tokens_in=response.tokens_in,
        tokens_out=response.tokens_out,
        latency_ms=response.latency_ms,
        cached=response.cached,
    )
