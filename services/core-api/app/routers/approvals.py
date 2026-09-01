"""Phase 35 A — HITL approvals (§12, §14 POST /approvals/{id}/decision).

V1 stub: standalone CRUD + decision endpoint. No workflow pause/resume yet —
that requires executor integration (V2). This satisfies Security Center →
Approvals UI and the /api/v1/approvals contract.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.approval import STATUS_APPROVED, STATUS_PENDING, STATUS_REJECTED, Approval
from app.models.notification import Notification
from app.models.user import User

router = APIRouter(prefix="/approvals", tags=["approvals"])


class ApprovalCreate(BaseModel):
    action: str = Field(min_length=1, max_length=128, examples=["execute_code: sandbox deploy"])
    agent_id: str | None = Field(default=None, max_length=64)
    workflow_id: str | None = Field(default=None, description="UUID string if linked to a workflow")
    payload: dict | None = None


class ApprovalOut(BaseModel):
    id: uuid.UUID
    action: str
    agent_id: str | None
    workflow_id: uuid.UUID | None
    status: str
    payload: dict | None
    decision_reason: str | None
    created_at: datetime
    updated_at: datetime


class DecisionRequest(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    reason: str | None = Field(default=None, max_length=1000)


def _to_out(a: Approval) -> ApprovalOut:
    return ApprovalOut(
        id=a.id,
        action=a.action,
        agent_id=a.agent_id,
        workflow_id=a.workflow_id,
        status=a.status,
        payload=a.payload,
        decision_reason=a.decision_reason,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


@router.get("", response_model=list[ApprovalOut])
async def list_approvals(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ApprovalOut]:
    result = await db.execute(
        select(Approval).where(Approval.user_id == current_user.id).order_by(Approval.created_at.desc()).limit(100)
    )
    return [_to_out(a) for a in result.scalars().all()]


@router.post("", response_model=ApprovalOut, status_code=status.HTTP_201_CREATED)
async def create_approval(
    payload: ApprovalCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApprovalOut:
    wid = None
    if payload.workflow_id:
        try:
            wid = uuid.UUID(payload.workflow_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid workflow_id UUID")
    row = Approval(
        user_id=current_user.id,
        workflow_id=wid,
        agent_id=payload.agent_id,
        action=payload.action.strip(),
        payload=payload.payload,
        status=STATUS_PENDING,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.get("/{approval_id}", response_model=ApprovalOut)
async def get_approval(
    approval_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApprovalOut:
    row = await db.get(Approval, approval_id)
    if row is None or row.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")
    return _to_out(row)


@router.post("/{approval_id}/decision", response_model=ApprovalOut)
async def decide_approval(
    approval_id: uuid.UUID,
    payload: DecisionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApprovalOut:
    row = await db.get(Approval, approval_id)
    if row is None or row.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")
    if row.status != STATUS_PENDING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Already {row.status}")
    row.status = STATUS_APPROVED if payload.decision == "approved" else STATUS_REJECTED
    row.decision_reason = payload.reason
    # side-effect: create a notification so the UI inbox reflects the decision
    db.add(
        Notification(
            user_id=current_user.id,
            type="approval",
            title=f"Approval {row.status}: {row.action[:80]}",
            message=payload.reason or f"Decision: {payload.decision} for {row.action}",
            link=f"/approvals",
        )
    )
    await db.commit()
    await db.refresh(row)
    return _to_out(row)
