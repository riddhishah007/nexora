"""Phase 13 — Coding Agent + sandbox endpoints (§5, §28, §27).

POST /api/v1/code/generate — LLM -> code (no exec)
POST /api/v1/code/execute — direct sandboxed exec of supplied code
POST /api/v1/code/run     — generate + exec + synthesize (coding-agent)
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import AGENT_REGISTRY
from app.database import get_db
from app.dependencies import get_current_user
from app.llm.gateway import LLMGateway
from app.models.user import User
from app.tools import ToolContext

router = APIRouter(prefix="/code", tags=["code"])


class CodeGenerateRequest(BaseModel):
    task: str = Field(min_length=1, max_length=4000, description="Natural language coding task")


class CodeGenerateResponse(BaseModel):
    code: str
    provider: str
    model: str
    latency_ms: int
    mock: bool


class CodeExecuteRequest(BaseModel):
    code: str = Field(min_length=1, max_length=30000)
    language: str = Field(default="python", pattern="^(python|py)$")
    timeout_seconds: float | None = Field(default=None, ge=1, le=15)


class CodeExecuteResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    truncated: bool
    timeout: bool


class CodeRunRequest(BaseModel):
    task: str = Field(min_length=1, max_length=4000)
    code: str | None = Field(default=None, max_length=30000)
    execute: bool = True
    language: str = Field(default="python", pattern="^(python|py)$")


class CodeRunResponse(BaseModel):
    answer: str
    code: str | None = None
    execution: CodeExecuteResponse | None = None
    provider: str
    model: str
    latency_ms: int
    mock: bool


@router.post("/generate", response_model=CodeGenerateResponse)
async def code_generate(
    payload: CodeGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CodeGenerateResponse:
    agent = AGENT_REGISTRY.get("coding-agent")
    if agent is None:
        raise HTTPException(status_code=503, detail="Coding agent unavailable")
    code, llm = await agent.generate(payload.task, db, user_id=str(current_user.id))
    await LLMGateway.record_usage(db, current_user.id, llm)
    return CodeGenerateResponse(code=code, provider=llm.provider, model=llm.model, latency_ms=llm.latency_ms, mock=llm.mock)


@router.post("/execute", response_model=CodeExecuteResponse)
async def code_execute(
    payload: CodeExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CodeExecuteResponse:
    from app.tools import get_tool_registry

    registry = get_tool_registry()
    ctx = ToolContext(agent_id="coding-agent", user_id=str(current_user.id), permissions=["code:execute"])
    tool_payload: dict = {"code": payload.code, "language": payload.language}
    if payload.timeout_seconds is not None:
        tool_payload["timeout_seconds"] = payload.timeout_seconds
    result = await registry.execute("execute_code", tool_payload, ctx, db=db)
    if not result.ok:
        raise HTTPException(status_code=400, detail=result.error or "execution failed")
    data = result.data or {}
    return CodeExecuteResponse(**{k: data.get(k) for k in CodeExecuteResponse.model_fields})


@router.post("/run", response_model=CodeRunResponse)
async def code_run(
    payload: CodeRunRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CodeRunResponse:
    agent = AGENT_REGISTRY.get("coding-agent")
    if agent is None:
        raise HTTPException(status_code=503, detail="Coding agent unavailable")
    answer, exec_data, llm = await agent.run(
        payload.task, db, user_id=str(current_user.id), execute=payload.execute, code=payload.code,
    )
    await LLMGateway.record_usage(db, current_user.id, llm)
    # extract code fence from answer for convenience
    import re as _re
    m = _re.search(r"```(?:python|py)?\s*\n?(.*?)```", answer, _re.DOTALL | _re.IGNORECASE)
    code_out = m.group(1).strip() if m else None
    exec_resp = None
    if exec_data:
        exec_resp = CodeExecuteResponse(
            stdout=exec_data.get("stdout",""),
            stderr=exec_data.get("stderr",""),
            exit_code=int(exec_data.get("exit_code",0)),
            duration_ms=int(exec_data.get("duration_ms",0)),
            truncated=bool(exec_data.get("truncated", False)),
            timeout=bool(exec_data.get("timeout", False)),
        )
    return CodeRunResponse(answer=answer, code=code_out, execution=exec_resp, provider=llm.provider, model=llm.model, latency_ms=llm.latency_ms, mock=llm.mock)
