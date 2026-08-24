"""Phase 15 — Real-time agent network (§19) WebSocket.

GET /api/v1/ws/workflows/{workflow_id}?token=...
Publishes workflow-scoped events from Redis pub/sub (nexora:workflow:{id}).
Falls back to polling if Redis is unavailable.

Safe execution display: only pre-approved status strings are emitted
(AGENT_STARTED etc. with agent_id/instruction) — never raw LLM chain-of-thought (§22).
"""

import asyncio
import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import SessionFactory
from app.models.workflow import Workflow, WorkflowStep
from app.security.tokens import TOKEN_TYPE_ACCESS, TokenError, decode_token

router = APIRouter(prefix="/ws", tags=["realtime"])

def _channel(workflow_id: str) -> str:
    return f"nexora:workflow:{workflow_id}"

async def _get_user_from_token(token: str):
    try:
        payload = decode_token(token, expected_type=TOKEN_TYPE_ACCESS)
        user_id = uuid.UUID(payload["sub"])
    except (TokenError, ValueError, KeyError):
        return None
    # fetch user
    async with SessionFactory() as db:
        from app.models.user import User
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user and user.is_active:
            return user
    return None

@router.websocket("/workflows/{workflow_id}")
async def workflow_ws(websocket: WebSocket, workflow_id: str):
    # --- auth via ?token=... or Authorization header ---
    token = websocket.query_params.get("token") or websocket.query_params.get("access_token")
    if not token:
        auth = websocket.headers.get("authorization") or websocket.headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user = await _get_user_from_token(token)
    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # validate workflow ownership
    try:
        wf_uuid = uuid.UUID(workflow_id)
    except ValueError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    async with SessionFactory() as db:
        result = await db.execute(select(Workflow).where(Workflow.id == wf_uuid, Workflow.user_id == user.id))
        workflow = result.scalar_one_or_none()
        if workflow is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        steps = (await db.execute(select(WorkflowStep).where(WorkflowStep.workflow_id == wf_uuid).order_by(WorkflowStep.seq))).scalars().all()

    await websocket.accept()
    # initial snapshot
    await websocket.send_text(json.dumps({
        "type": "CONNECTED",
        "workflow_id": workflow_id,
        "data": {
            "status": workflow.status,
            "steps": [{"seq": s.seq, "agent_id": s.agent_id, "status": s.status, "depends_on": s.depends_on} for s in steps],
        },
    }))

    # try Redis pub/sub, fallback to polling
    redis = None
    pubsub = None
    use_redis = False
    try:
        if settings.redis_url:
            import redis.asyncio as aioredis  # type: ignore
            redis = aioredis.from_url(settings.redis_url, decode_responses=True)
            pubsub = redis.pubsub()
            await pubsub.subscribe(_channel(workflow_id))
            use_redis = True
    except Exception:
        use_redis = False
        if pubsub:
            try:
                await pubsub.close()
            except Exception:
                pass
        if redis:
            try:
                await redis.close()
            except Exception:
                pass
        redis = pubsub = None

    # concurrent tasks: redis listener <-> websocket ping
    async def redis_listener():
        if not use_redis or pubsub is None:
            return
        async for msg in pubsub.listen():  # type: ignore[union-attr]
            if msg.get("type") != "message":
                continue
            try:
                await websocket.send_text(msg["data"])
            except (WebSocketDisconnect, RuntimeError):
                break

    async def ws_reader():
        try:
            while True:
                # wait for client ping/close; timeout to keep alive
                try:
                    await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                    # echo pong
                    await websocket.send_text(json.dumps({"type": "PONG"}))
                except asyncio.TimeoutError:
                    # keepalive
                    try:
                        await websocket.ping()
                    except Exception:
                        break
                except WebSocketDisconnect:
                    break
                except Exception:
                    break
        except asyncio.CancelledError:
            pass

    async def polling_fallback():
        if use_redis:
            return
        # poll workflow status every 700ms, emit diff
        last_status = workflow.status
        last_step_status = {s.seq: s.status for s in steps}
        try:
            while True:
                await asyncio.sleep(0.7)
                async with SessionFactory() as db:
                    r = await db.execute(select(Workflow).where(Workflow.id == wf_uuid))
                    wf = r.scalar_one_or_none()
                    if wf is None:
                        break
                    s_rows = (await db.execute(select(WorkflowStep).where(WorkflowStep.workflow_id == wf_uuid).order_by(WorkflowStep.seq))).scalars().all()
                    # emit status changes
                    if wf.status != last_status:
                        await websocket.send_text(json.dumps({"type": "WORKFLOW_COMPLETED" if wf.status in ("done","failed") else "WORKFLOW_STARTED", "workflow_id": workflow_id, "data": {"status": wf.status}}))
                        last_status = wf.status
                    for s in s_rows:
                        if last_step_status.get(s.seq) != s.status:
                            ev = "AGENT_COMPLETED" if s.status == "done" else "AGENT_FAILED" if s.status == "failed" else "AGENT_STARTED" if s.status == "running" else "AGENT_SELECTED"
                            await websocket.send_text(json.dumps({"type": ev, "workflow_id": workflow_id, "data": {"seq": s.seq, "agent_id": s.agent_id, "status": s.status}}))
                            last_step_status[s.seq] = s.status
                    if wf.status in ("done", "failed"):
                        await websocket.send_text(json.dumps({"type": "FINAL_RESPONSE_READY", "workflow_id": workflow_id, "data": {}}))
                        break
        except (WebSocketDisconnect, RuntimeError, asyncio.CancelledError):
            pass
        except Exception:
            pass

    # run listeners
    tasks = []
    if use_redis:
        tasks.append(asyncio.create_task(redis_listener()))
    else:
        tasks.append(asyncio.create_task(polling_fallback()))
    tasks.append(asyncio.create_task(ws_reader()))

    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
    finally:
        if pubsub is not None:
            try:
                await pubsub.unsubscribe(_channel(workflow_id))
                await pubsub.close()
            except Exception:
                pass
        if redis is not None:
            try:
                await redis.close()
            except Exception:
                pass
        try:
            await websocket.close()
        except Exception:
            pass
