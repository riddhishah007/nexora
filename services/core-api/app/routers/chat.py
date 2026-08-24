import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.llm import get_llm_gateway
from app.llm.gateway import LLMGateway
from app.models.conversation import Conversation, Message
from app.models.user import User
from app.models.workflow import (
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PLANNING,
    STATUS_RUNNING,
    Workflow,
    WorkflowStep,
)
from app.orchestrator import Planner, execute_workflow, workflow_name
from app.orchestrator.executor import synthesize_final_answer

router = APIRouter(tags=["chat"])

_planner = Planner(gateway=get_llm_gateway())


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: uuid.UUID | None = None


class PlanStepOut(BaseModel):
    seq: int
    agent_id: str
    instruction: str
    depends_on: list[int]
    status: str


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    workflow_id: uuid.UUID
    status: str
    steps: list[PlanStepOut]


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: str


class ConversationSummary(BaseModel):
    id: uuid.UUID
    title: str
    created_at: str


class ConversationDetail(ConversationSummary):
    messages: list[MessageOut]


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    # Phase 17: prompt-injection scan before any agent sees the input
    from app.security.events import log_security_event
    from app.security.injection import scan as injection_scan

    scan = injection_scan(payload.message)
    if scan["should_block"]:
        try:
            await log_security_event(
                db,
                event_type="prompt_injection",
                risk_level=scan["risk_level"],
                blocked=True,
                user_id=current_user.id,
                details={"score": scan["score"], "matched": scan["matched"], "message_preview": payload.message[:300]},
                ip_address=request.client.host if request.client else None,
            )
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Blocked: potential prompt injection detected (risk={scan['risk_level']}, score={scan['score']}) — matched: {', '.join(scan['matched'][:3])}",
        )
    elif scan["score"] > 0:
        # log medium/low risk but allow
        try:
            await log_security_event(
                db,
                event_type="prompt_injection",
                risk_level=scan["risk_level"],
                blocked=False,
                user_id=current_user.id,
                details={"score": scan["score"], "matched": scan["matched"]},
                ip_address=request.client.host if request.client else None,
            )
        except Exception:
            pass

    if payload.conversation_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == payload.conversation_id,
                Conversation.user_id == current_user.id,
            )
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
    else:
        conversation = Conversation(
            user_id=current_user.id,
            title=payload.message.strip()[:80] or "New chat",
        )
        db.add(conversation)
        await db.flush()

    user_message = Message(
        conversation_id=conversation.id, role="user", content=payload.message
    )
    db.add(user_message)

    workflow = Workflow(
        user_id=current_user.id,
        conversation_id=conversation.id,
        name=workflow_name(payload.message),
        status=STATUS_PLANNING,
        definition={"request": payload.message},
    )
    db.add(workflow)
    await db.commit()

    plan, llm = await _planner.build_plan(payload.message)
    await LLMGateway.record_usage(db, current_user.id, llm)

    step_rows = [
        WorkflowStep(
            workflow_id=workflow.id,
            seq=i,
            agent_id=s.agent_id,
            instruction=s.instruction,
            depends_on=s.depends_on,
        )
        for i, s in enumerate(plan)
    ]
    db.add_all(step_rows)
    workflow.status = STATUS_RUNNING
    await db.commit()

    # Phase 15: emit TASK_CREATED / AGENT_SELECTED early
    try:
        from app.events.bus import emit as _emit
        await _emit(str(workflow.id), "TASK_CREATED", {"conversation_id": str(conversation.id), "steps": len(step_rows), "agents": [s.agent_id for s in step_rows]})
        for s in step_rows:
            await _emit(str(workflow.id), "AGENT_SELECTED", {"seq": s.seq, "agent_id": s.agent_id})
    except Exception:
        pass

    ok = await execute_workflow(db, step_rows, current_user.id)
    workflow.status = STATUS_DONE if ok else STATUS_FAILED

    # Phase 14 synthesis: combine parallel branch outputs when >1 successful step.
    synth_text, synth_llm = await synthesize_final_answer(step_rows, str(current_user.id))
    if synth_llm is not None:
        try:
            await LLMGateway.record_usage(db, current_user.id, synth_llm)
        except Exception:
            pass
        final_answer = synth_text
        try:
            from app.events.bus import emit as _emit2
            await _emit2(str(workflow.id), "FINAL_RESPONSE_READY", {"synthesized": True, "length": len(final_answer)})
        except Exception:
            pass
    else:
        # single-step or no synthesis needed
        final_answer = synth_text if synth_text else next(
            (s.output.get("answer") for s in reversed(step_rows) if s.output and "answer" in s.output),
            "Plan executed.",
        )
        try:
            from app.events.bus import emit as _emit3
            await _emit3(str(workflow.id), "FINAL_RESPONSE_READY", {"synthesized": False, "length": len(final_answer)})
        except Exception:
            pass
    db.add(
        Message(
            conversation_id=conversation.id,
            role="assistant",
            content=str(final_answer),
            workflow_id=workflow.id,
        )
    )
    await db.commit()

    return ChatResponse(
        conversation_id=conversation.id,
        workflow_id=workflow.id,
        status=workflow.status,
        steps=[
            PlanStepOut(
                seq=s.seq,
                agent_id=s.agent_id,
                instruction=s.instruction,
                depends_on=s.depends_on,
                status=s.status,
            )
            for s in step_rows
        ],
    )


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationSummary]:
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.created_at.desc())
    )
    return [
        ConversationSummary(
            id=c.id, title=c.title, created_at=c.created_at.isoformat()
        )
        for c in result.scalars()
    ]


@router.get(
    "/conversations/{conversation_id}", response_model=ConversationDetail
)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetail:
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at.isoformat(),
        messages=[
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                created_at=m.created_at.isoformat(),
            )
            for m in conversation.messages
        ],
    )
