import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.workflow import Workflow, WorkflowStep

router = APIRouter(prefix="/workflows", tags=["workflows"])


class StepOut(BaseModel):
    seq: int
    agent_id: str
    instruction: str
    depends_on: list[int]
    status: str
    output: dict | None


class WorkflowOut(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    steps: list[StepOut]


@router.get("/{workflow_id}", response_model=WorkflowOut)
async def get_workflow(
    workflow_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowOut:
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.user_id == current_user.id,
        )
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    steps = (
        (
            await db.execute(
                select(WorkflowStep)
                .where(WorkflowStep.workflow_id == workflow.id)
                .order_by(WorkflowStep.seq)
            )
        )
        .scalars()
        .all()
    )
    return WorkflowOut(
        id=workflow.id,
        name=workflow.name,
        status=workflow.status,
        steps=[
            StepOut(
                seq=s.seq,
                agent_id=s.agent_id,
                instruction=s.instruction,
                depends_on=s.depends_on or [],
                status=s.status,
                output=s.output,
            )
            for s in steps
        ],
    )
