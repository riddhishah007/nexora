"""Phase 16 — Redis queue bus (§18).

Simple LPUSH/BRPOP over Redis, with DB-backed Job rows for persistence,
idempotency, retries and polling. If Redis is down, falls back to direct
DB status (jobs remain queued until worker polls DB — not ideal but safe).
"""

import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.job import JOB_QUEUED, Job

DEFAULT_QUEUE = "nexora:queue:default"
_redis = None

def _get_redis():
    global _redis
    if _redis is not None:
        return _redis
    if not settings.redis_url:
        return None
    try:
        import redis.asyncio as aioredis  # type: ignore
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        return _redis
    except Exception:
        return None

async def enqueue(
    db: AsyncSession,
    user_id: uuid.UUID | str,
    job_type: str,
    payload: dict,
    idempotency_key: str | None = None,
    queue: str = DEFAULT_QUEUE,
) -> Job:
    """Create a Job row and push its id to Redis. Idempotent if key matches an existing queued/running job."""
    if isinstance(user_id, str):
        user_id = uuid.UUID(user_id)
    # idempotency: if a job with same key is already queued/running, return it
    if idempotency_key:
        existing = await db.execute(
            select(Job).where(Job.idempotency_key == idempotency_key, Job.user_id == user_id, Job.status.in_(["queued", "running"]))
        )
        job = existing.scalar_one_or_none()
        if job:
            return job

    job = Job(
        user_id=user_id,
        type=job_type,
        payload=payload,
        status=JOB_QUEUED,
        idempotency_key=idempotency_key,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    # push to redis after commit so worker can see the row (avoid race)
    try:
        redis = _get_redis()
        if redis is not None:
            await redis.lpush(queue, json.dumps({"job_id": str(job.id), "type": job_type}))
        # also publish for WS
        from app.events.bus import emit
        await emit(str(job.id), "TASK_CREATED", {"job_id": str(job.id), "type": job_type})
    except Exception as exc:  # noqa: BLE001
        print(f"[queue] enqueue redis push failed: {exc}")
    return job

async def get_queue_length(queue: str = DEFAULT_QUEUE) -> int:
    try:
        redis = _get_redis()
        if redis is None:
            return 0
        return await redis.llen(queue)
    except Exception:
        return 0
