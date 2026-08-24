"""Phase 15 — Event bus (§19) over Redis pub/sub.

Frontend subscribes via WebSocket /api/v1/ws/workflows/{id} and receives
workflow-scoped events. Publishing is best-effort: if Redis is down, events
are just logged (so the pipeline never fails because of the bus).
"""

import json
from datetime import datetime, timezone
from typing import Any

from app.config import settings

# Event types exactly as listed in blueprint §19 (plus TASK_CREATED/AGENT_SELECTED)
EVENT_TYPES = {
    "TASK_CREATED",
    "AGENT_SELECTED",
    "AGENT_STARTED",
    "TOOL_STARTED",
    "TOOL_COMPLETED",
    "AGENT_COMPLETED",
    "AGENT_FAILED",
    "WORKFLOW_COMPLETED",
    "FINAL_RESPONSE_READY",
    "WORKFLOW_STARTED",
}

def _channel(workflow_id: str) -> str:
    return f"nexora:workflow:{workflow_id}"

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

async def emit(workflow_id: str | Any, event_type: str, data: dict | None = None) -> None:
    """Publish an event to the workflow's channel. Never raises."""
    if event_type not in EVENT_TYPES:
        # allow extra types but log
        pass
    try:
        redis = _get_redis()
        if redis is None:
            return
        payload = {
            "type": event_type,
            "workflow_id": str(workflow_id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data or {},
        }
        await redis.publish(_channel(str(workflow_id)), json.dumps(payload))
    except Exception as exc:  # noqa: BLE001 — bus is best-effort
        # Don't break the pipeline because the bus is down
        print(f"[event-bus] publish failed {event_type}: {exc}")

# For graceful shutdown, allow explicit close
async def close():
    global _redis
    if _redis is not None:
        try:
            await _redis.close()
        except Exception:
            pass
        _redis = None
