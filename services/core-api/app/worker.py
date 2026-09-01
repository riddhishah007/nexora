"""Phase 16 — Background worker (§18).

Consumes nexora:queue:default (LPUSH/BRPOP) and processes rag_ingest jobs.
Also polls DB for queued jobs if Redis is unavailable (fallback).

Each job is a row in `jobs` with status queued->running->done/failed.
Retries: 3 attempts with exponential backoff, then dead.
Idempotency via idempotency_key already handled at enqueue time.

Run via: python -m worker.worker  (WORKDIR /app, PYTHONPATH /app)
"""

import asyncio
import json
import uuid

from sqlalchemy import select

from app.config import settings
from app.database import SessionFactory
from app.models.job import JOB_DEAD, JOB_DONE, JOB_FAILED, JOB_QUEUED, JOB_RUNNING, JOB_TYPE_RAG_INGEST, Job

QUEUE = "nexora:queue:default"
POLL_INTERVAL = 2.0  # when redis empty, also poll DB for orphaned queued jobs
MAX_ATTEMPTS = 3
RETRY_DELAYS = [2, 4, 8]  # seconds per attempt

def _get_redis():
    if not settings.redis_url:
        return None
    try:
        import redis.asyncio as aioredis  # type: ignore
        return aioredis.from_url(settings.redis_url, decode_responses=True)
    except Exception as exc:
        print(f"[worker] redis unavailable: {exc}")
        return None

async def process_rag_ingest(job: Job, db):
    from app.llm import get_llm_gateway
    from app.rag.service import ingest_document

    payload = job.payload or {}
    document_id = payload.get("document_id")
    user_id = str(job.user_id)
    if not document_id:
        raise ValueError("rag_ingest payload missing document_id")
    gateway = get_llm_gateway()
    result = await ingest_document(document_id=document_id, db=db, gateway=gateway, user_id=user_id)
    return result

async def handle_job(job_id: str):
    async with SessionFactory() as db:
        job = await db.get(Job, uuid.UUID(job_id))
        if job is None:
            print(f"[worker] job {job_id} not found")
            return
        if job.status not in (JOB_QUEUED, JOB_RUNNING):
            print(f"[worker] job {job_id} status {job.status} skip")
            return
        # mark running
        job.status = JOB_RUNNING
        job.attempts = (job.attempts or 0) + 1
        await db.commit()
        print(f"[worker] processing {job.type} {job.id} attempt {job.attempts}")

        # publish WS event: job started
        try:
            from app.events.bus import emit
            await emit(str(job.id), "AGENT_STARTED", {"job_id": str(job.id), "type": job.type, "attempt": job.attempts})
            # also publish to workflow-style channel for jobs polling fallback
            await emit(str(job.user_id), "TOOL_STARTED", {"job_id": str(job.id)})
        except Exception:
            pass

        try:
            if job.type == JOB_TYPE_RAG_INGEST:
                result = await process_rag_ingest(job, db)
                job.status = JOB_DONE
                job.result = result
                job.error = None
                await db.commit()
                print(f"[worker] done {job.id} chunks={result.get('chunks')}")
                try:
                    from app.events.bus import emit as _emit
                    await _emit(str(job.id), "AGENT_COMPLETED", {"job_id": str(job.id), "result": result})
                    await _emit(str(job.user_id), "TOOL_COMPLETED", {"job_id": str(job.id)})
                except Exception:
                    pass
            else:
                raise ValueError(f"unknown job type {job.type}")

        except Exception as exc:  # noqa: BLE001
            err = str(exc)[:500]
            print(f"[worker] job {job.id} failed: {err}")
            # decide retry
            if job.attempts < MAX_ATTEMPTS:
                job.status = JOB_QUEUED
                job.error = err
                await db.commit()
                # requeue with delay
                delay = RETRY_DELAYS[min(job.attempts - 1, len(RETRY_DELAYS) - 1)]
                await asyncio.sleep(delay)
                # push back to redis
                try:
                    redis = _get_redis()
                    if redis is not None:
                        await redis.lpush(QUEUE, json.dumps({"job_id": str(job.id), "type": job.type}))
                        print(f"[worker] requeued {job.id} after {delay}s")
                    else:
                        print(f"[worker] redis unavailable, job {job.id} will be picked up via DB poll")
                except Exception as e:
                    print(f"[worker] requeue failed {e}")
                try:
                    from app.events.bus import emit as _emit
                    await _emit(str(job.id), "AGENT_FAILED", {"job_id": str(job.id), "error": err, "retry": True})
                except Exception:
                    pass
            else:
                job.status = JOB_DEAD
                job.error = err
                await db.commit()
                print(f"[worker] job {job.id} dead after {job.attempts} attempts")
                try:
                    from app.events.bus import emit as _emit
                    await _emit(str(job.id), "AGENT_FAILED", {"job_id": str(job.id), "error": err})
                except Exception:
                    pass

async def main():
    print("[worker] starting, redis:", settings.redis_url[:20] if settings.redis_url else "none")
    # ensure DB is ready (wait for postgres)
    for i in range(10):
        try:
            async with SessionFactory() as db:
                await db.execute(select(Job).limit(1))
            print("[worker] db ready")
            break
        except Exception as e:
            print(f"[worker] db not ready {e}, retry {i}")
            await asyncio.sleep(2)
    else:
        print("[worker] db failed to connect, exiting")
        return

    redis = _get_redis()
    if redis is None:
        print("[worker] redis not available, falling back to DB poll only")
    else:
        print(f"[worker] subscribed to {QUEUE}")

    while True:
        job_id = None
        job_type = None
        # try redis BRPOP
        if redis is not None:
            try:
                res = await redis.brpop(QUEUE, timeout=5)
                if res:
                    _, raw = res
                    data = json.loads(raw)
                    job_id = data.get("job_id")
                    job_type = data.get("type")
                    print(f"[worker] popped {job_id} type {job_type} from redis")
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[worker] brpop error {e}")
                await asyncio.sleep(1)

        # fallback: poll DB for oldest queued job if nothing from redis
        if job_id is None:
            try:
                async with SessionFactory() as db:
                    result = await db.execute(
                        select(Job).where(Job.status == JOB_QUEUED).order_by(Job.created_at).limit(1)
                    )
                    job = result.scalar_one_or_none()
                    if job:
                        job_id = str(job.id)
                        print(f"[worker] polled DB job {job_id}")
                    else:
                        await asyncio.sleep(POLL_INTERVAL)
                        continue
            except Exception as e:
                print(f"[worker] db poll failed {e}")
                await asyncio.sleep(POLL_INTERVAL)
                continue

        if job_id:
            try:
                await handle_job(job_id)
            except Exception as e:
                print(f"[worker] handle_job {job_id} crashed {e}")
                await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[worker] interrupted")
