"""Phase 32: request-ID + structured log + Prometheus counters middleware.

- Assigns `X-Request-ID` (reuse inbound header or uuid4) to every response.
- Emits one structured JSON log per request (method, path, status, duration_ms, request_id, user?).
- Maintains in-memory counters for `/metrics` (no external dep: avoids adding prometheus_client).

Counters are process-local and reset on restart — sufficient for MVP/portfolio
observability without pulling in an extra exporter. Shape mirrors Prometheus
text exposition format.
"""

from __future__ import annotations

import json
import time
import uuid
from collections import Counter, defaultdict

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# Global counters — imported by the /metrics router
http_requests_total: Counter[str] = Counter()
http_requests_by_status: Counter[str] = Counter()
http_request_duration_ms_sum: defaultdict[str, float] = defaultdict(float)
http_request_duration_ms_count: defaultdict[str, int] = defaultdict(int)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        req_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request.state.request_id = req_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # log even on unhandled error
            dur = int((time.perf_counter() - start) * 1000)
            _log(request, 500, dur, req_id)
            raise
        dur = int((time.perf_counter() - start) * 1000)
        response.headers["X-Request-ID"] = req_id

        # counters
        route = request.url.path
        # normalize dynamic segments to keep cardinality bounded
        # e.g. /api/v1/workflows/<uuid> -> /api/v1/workflows/:id
        norm = _normalize_path(route)
        key = f'{norm}|{request.method}'
        http_requests_total[key] += 1
        http_requests_by_status[f'{norm}|{response.status_code}'] += 1
        http_request_duration_ms_sum[key] += dur
        http_request_duration_ms_count[key] += 1

        _log(request, response.status_code, dur, req_id)
        return response


def _normalize_path(path: str) -> str:
    # replace uuids and long hex ids
    import re

    # uuid v4
    path = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", ":id", path, flags=re.I)
    # 12+ hex chunks (stored_name)
    path = re.sub(r"/[0-9a-f]{32,}", "/:id", path, flags=re.I)
    return path


def _log(request: Request, status: int, dur_ms: int, req_id: str) -> None:
    try:
        # user id if JWT was parsed; best-effort
        uid = getattr(request.state, "user_id", None)
        rec = {
            "level": "info" if status < 400 else "warn" if status < 500 else "error",
            "method": request.method,
            "path": request.url.path,
            "status": status,
            "duration_ms": dur_ms,
            "request_id": req_id,
            "user_id": str(uid) if uid else None,
        }
        # single-line JSON to stdout — picked up by `docker logs` / any log aggregator
        print(json.dumps(rec), flush=True)
    except Exception:
        pass

    # Also expose counters snapshot for /metrics route to format
