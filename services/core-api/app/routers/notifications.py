"""Phase 35 A — Notifications inbox (§4 V1 notifications)."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.notification import Notification
from app.models.user import User

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    message: str
    read: bool
    link: str | None
    created_at: datetime


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    unread_only: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[NotificationOut]:
    q = select(Notification).where(Notification.user_id == current_user.id).order_by(Notification.created_at.desc()).limit(100)
    if unread_only:
        q = q.where(Notification.read == False)  # noqa: E712
    result = await db.execute(q)
    return [
        NotificationOut(id=n.id, type=n.type, title=n.title, message=n.message, read=n.read, link=n.link, created_at=n.created_at)
        for n in result.scalars().all()
    ]


@router.post("/{notification_id}/read", response_model=NotificationOut)
async def mark_read(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationOut:
    row = await db.get(Notification, notification_id)
    if row is None or row.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    row.read = True
    await db.commit()
    await db.refresh(row)
    return NotificationOut(id=row.id, type=row.type, title=row.title, message=row.message, read=row.read, link=row.link, created_at=row.created_at)


@router.post("/read-all", response_model=dict)
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Notification).where(Notification.user_id == current_user.id, Notification.read == False))  # noqa: E712
    for n in result.scalars().all():
        n.read = True
    await db.commit()
    return {"status": "ok"}


# helper used by other routers to create notifications without exposing raw model
async def create_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    type: str,
    title: str,
    message: str,
    link: str | None = None,
) -> Notification:
    row = Notification(user_id=user_id, type=type, title=title, message=message, link=link)
    db.add(row)
    await db.flush()
    return row
