"""Phase 35 A — Exports (§4 V1 exports).

Generates markdown/PDF-ready exports from a workflow's synthesis or a
conversation's messages. V1: markdown export (PDF stub deferred — client can
print to PDF). Returns the export as downloadable markdown.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.conversation import Conversation, Message
from app.models.user import User
from app.models.workflow import Workflow, WorkflowStep

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/workflow/{workflow_id}", response_class=PlainTextResponse)
async def export_workflow(
    workflow_id: uuid.UUID,
    format: str = Query(default="md", pattern="^(md|markdown)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> str:
    wf = await db.get(Workflow, workflow_id)
    if wf is None or wf.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Workflow not found")
    steps = (await db.execute(select(WorkflowStep).where(WorkflowStep.workflow_id == wf.id).order_by(WorkflowStep.seq))).scalars().all()
    synthesis = (wf.definition or {}).get("synthesis", "")
    lines = [f"# {wf.name}", "", f"_Workflow {wf.id} · status: {wf.status}_", ""]
    lines.append("## Steps")
    for s in steps:
        out = (s.output or {}).get("answer", "") if s.output else ""
        lines += [f"### {s.seq}. {s.agent_id}", f"_{s.instruction}_", "", f"Status: {s.status}", ""]
        if out:
            lines += [out[:1200], ""]
    if synthesis:
        lines += ["## Synthesis", "", synthesis[:8000], ""]
    return "\n".join(lines)


@router.get("/conversation/{conversation_id}", response_class=PlainTextResponse)
async def export_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> str:
    conv = await db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    msgs = (await db.execute(select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at))).scalars().all()
    lines = [f"# {conv.title}", "", f"_Conversation {conv.id}_", ""]
    for m in msgs:
        lines += [f"### {m.role}", "", m.content[:4000], ""]
    return "\n".join(lines)
