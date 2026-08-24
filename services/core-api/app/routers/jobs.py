"""Phase 16 — Jobs/queue polling (§18)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.job import Job
from app.models.user import User
from app.queue.bus import get_queue_length

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.get("/queue/length")
async def queue_length():
    length = await get_queue_length()
    return {"queue": "nexora:queue:default", "length": length}

@router.get("/{job_id}")
async def get_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        jid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found") from None
    job = await db.get(Job, jid)
    if job is None or str(job.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": str(job.id),
        "type": job.type,
        "status": job.status,
        "payload": job.payload,
        "result": job.result,
        "error": job.error,
        "attempts": job.attempts,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }

@router.get("")
async def list_jobs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Job).where(Job.user_id == current_user.id).order_by(Job.created_at.desc()).limit(20)
    )
    jobs = result.scalars().all()
    return [
        {
            "job_id": str(j.id),
            "type": j.type,
            "status": j.status,
            "payload": j.payload,
            "result": j.result,
            "error": j.error,
            "attempts": j.attempts,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in jobs
    ]
