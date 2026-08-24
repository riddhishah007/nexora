from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import AGENT_REGISTRY, REGISTRY_INFO
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

    # Normalize input: support both SearchAgentInput object and raw dict.
    raw: dict
    if isinstance(payload.input, dict):
        raw = payload.input
    else:
        # SearchAgentInput
        raw = payload.input.model_dump()

    agent = AGENT_REGISTRY[payload.agent_id]
    try:
        if payload.agent_id == "search-agent":
            query = raw.get("query") or raw.get("task") or ""
            answer, results, llm = await agent.run(query, db, user_id=str(current_user.id))
            await LLMGateway.record_usage(db, current_user.id, llm)
            return AgentRunResponse(
                agent_id=payload.agent_id,
                answer=answer,
                sources=[Source(title=r.get("title",""), url=r.get("url",""), score=float(r.get("score",0))) for r in results],
                provider=llm.provider, model=llm.model, latency_ms=llm.latency_ms, mock=llm.mock,
            )
        elif payload.agent_id == "rag-agent":
            query = raw.get("query") or raw.get("task") or ""
            answer, citations, llm = await agent.run(
                query, db, user_id=str(current_user.id),
                top_k=raw.get("top_k"), document_id=raw.get("document_id"),
            )
            await LLMGateway.record_usage(db, current_user.id, llm)
            return AgentRunResponse(
                agent_id=payload.agent_id, answer=answer, sources=[],
                provider=llm.provider, model=llm.model, latency_ms=llm.latency_ms, mock=llm.mock,
                citations=citations,
            )
        elif payload.agent_id == "pdf-agent":
            doc_id = raw.get("document_id") or raw.get("query") or ""
            answer, meta, llm = await agent.run(doc_id, db, user_id=str(current_user.id))
            await LLMGateway.record_usage(db, current_user.id, llm)
            return AgentRunResponse(
                agent_id=payload.agent_id, answer=answer, sources=[],
                provider=llm.provider, model=llm.model, latency_ms=llm.latency_ms, mock=llm.mock,
            )
        elif payload.agent_id == "coding-agent":
            task = raw.get("task") or raw.get("query") or ""
            code = raw.get("code")
            execute = raw.get("execute", True)
            # coerce str execute
            if isinstance(execute, str):
                execute = execute.lower() not in ("false", "0", "no")
            answer, exec_data, llm = await agent.run(task, db, user_id=str(current_user.id), execute=bool(execute), code=code)
            await LLMGateway.record_usage(db, current_user.id, llm)
            return AgentRunResponse(
                agent_id=payload.agent_id, answer=answer, sources=[],
                provider=llm.provider, model=llm.model, latency_ms=llm.latency_ms, mock=llm.mock,
                execution=exec_data,
            )
        else:
            # Fallback: try generic run(task)
            task = raw.get("task") or raw.get("query") or str(raw)
            answer, _results, llm = await agent.run(task, db, user_id=str(current_user.id))
            await LLMGateway.record_usage(db, current_user.id, llm)
            return AgentRunResponse(
                agent_id=payload.agent_id, answer=answer, sources=[],
                provider=llm.provider, model=llm.model, latency_ms=llm.latency_ms, mock=llm.mock,
            )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Agent execution failed: {exc}") from exc
