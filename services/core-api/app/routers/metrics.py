"""Phase 32: Prometheus-style /metrics endpoint (no extra dep).

Exposes:
- nexora_http_requests_total{route,method} counter
- nexora_http_requests_by_status{route,status} counter
- nexora_http_request_duration_ms_sum / _count (for avg latency)

Plus build info gauge.

Format is Prometheus text exposition (text/plain; version=0.0.4).
"""

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.middleware.request_id import (
    http_request_duration_ms_count,
    http_request_duration_ms_sum,
    http_requests_by_status,
    http_requests_total,
)

router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
async def metrics() -> str:
    lines: list[str] = []
    lines.append("# HELP nexora_http_requests_total Total HTTP requests by route and method")
    lines.append("# TYPE nexora_http_requests_total counter")
    for key, val in sorted(http_requests_total.items()):
        route, method = (key.split("|", 1) + [""])[:2]
        lines.append(f'nexora_http_requests_total{{route="{route}",method="{method}"}} {val}')

    lines.append("# HELP nexora_http_requests_by_status Requests by route and status")
    lines.append("# TYPE nexora_http_requests_by_status counter")
    for key, val in sorted(http_requests_by_status.items()):
        route, status = (key.split("|", 1) + [""])[:2]
        lines.append(f'nexora_http_requests_by_status{{route="{route}",status="{status}"}} {val}')

    lines.append("# HELP nexora_http_request_duration_ms_sum Sum of request durations")
    lines.append("# TYPE nexora_http_request_duration_ms_sum counter")
    for key, val in sorted(http_request_duration_ms_sum.items()):
        route, method = (key.split("|", 1) + [""])[:2]
        lines.append(f'nexora_http_request_duration_ms_sum{{route="{route}",method="{method}"}} {val:.1f}')

    lines.append("# HELP nexora_http_request_duration_ms_count Count of request durations")
    lines.append("# TYPE nexora_http_request_duration_ms_count counter")
    for key, val in sorted(http_request_duration_ms_count.items()):
        route, method = (key.split("|", 1) + [""])[:2]
        lines.append(f'nexora_http_request_duration_ms_count{{route="{route}",method="{method}"}} {val}')

    lines.append('# HELP nexora_build_info Build info')
    lines.append('# TYPE nexora_build_info gauge')
    lines.append('nexora_build_info{version="0.2.0",phase="32"} 1')

    return "\n".join(lines) + "\n"
