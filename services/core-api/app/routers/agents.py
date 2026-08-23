from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import AGENT_REGISTRY, REGISTRY_INFO, search_agent
from app.agents.schemas import AgentInfo, AgentRunRequest, AgentRunResponse, Source
from app.database import get_db
from app.dependencies import get_current_user
from app.llm.gateway import LLMGateway
from app.models.user import User

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=list[AgentInfo])
async def list_agents() -> list[AgentInfo]:
    return REGISTRY_INFO


@router.get("/{agent_id}", response_model=AgentInfo)
async def get_agent(agent_id: str) -> AgentInfo:
    for info in REGISTRY_INFO:
        if info.agent_id == agent_id:
            return info
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Unknown agent '{agent_id}'",
    )


@router.post("/run", response_model=AgentRunResponse)
async def run_agent(
    payload: AgentRunRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentRunResponse:
    if payload.agent_id not in AGENT_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown agent '{payload.agent_id}'",
        )

    try:
        answer, results, llm = await search_agent.run(
            payload.input.query, db, user_id=str(current_user.id)
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Agent execution failed; check server logs",
        )
    await LLMGateway.record_usage(db, current_user.id, llm)

    return AgentRunResponse(
        agent_id=payload.agent_id,
        answer=answer,
        sources=[
            Source(title=r["title"], url=r["url"], score=r["score"])
            for r in results
        ],
        provider=llm.provider,
        model=llm.model,
        latency_ms=llm.latency_ms,
        mock=llm.mock,
    )
