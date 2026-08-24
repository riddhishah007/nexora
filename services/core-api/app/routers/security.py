"""Phase 17 — Security Center (§26) + AI Security Monitor.

GET /api/v1/security/events — recent security_events (blocked injections, URL blocks, etc.)
GET /api/v1/security/audit  — recent audit_logs
GET /api/v1/security/health — 4-dimension health + rolling score
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.security_event import AuditLog, SecurityEvent
from app.models.user import User

router = APIRouter(prefix="/security", tags=["security"])

@router.get("/events")
async def list_security_events(
    limit: int = Query(default=50, ge=1, le=200),
    event_type: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # For demo, any authenticated user can see recent events (in prod, restrict to admin)
    q = select(SecurityEvent).order_by(SecurityEvent.created_at.desc()).limit(limit)
    if event_type:
        q = q.where(SecurityEvent.event_type == event_type)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "event_type": r.event_type,
            "agent_id": r.agent_id,
            "risk_level": r.risk_level,
            "blocked": r.blocked,
            "details": r.details,
            "user_id": str(r.user_id) if r.user_id else None,
            "ip_address": r.ip_address,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]

@router.get("/audit")
async def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))
    rows = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "action": r.action,
            "resource": r.resource,
            "resource_id": r.resource_id,
            "details": r.details,
            "user_id": str(r.user_id) if r.user_id else None,
            "ip_address": r.ip_address,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]

@router.get("/health")
async def security_health(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=24)

    # counts per dimension in last 24h
    async def count(event_types: list[str]) -> int:
        r = await db.execute(
            select(func.count()).select_from(SecurityEvent).where(
                SecurityEvent.created_at >= since,
                SecurityEvent.event_type.in_(event_types),
            )
        )
        return r.scalar() or 0

    async def score(event_types: list[str]) -> tuple[int, int, str]:
        cnt = await count(event_types)
        # also weight by risk
        r = await db.execute(
            select(SecurityEvent.risk_level, func.count()).where(
                SecurityEvent.created_at >= since,
                SecurityEvent.event_type.in_(event_types),
            ).group_by(SecurityEvent.risk_level)
        )
        risk_counts = {row[0]: row[1] for row in r.all()}
        # deduct: critical 15, high 10, medium 5, low 2 per event
        deductions = {"critical": 15, "high": 10, "medium": 5, "low": 2}
        total_ded = sum(deductions.get(k, 5) * v for k, v in risk_counts.items())
        # also base 3 per event if no risk breakdown (fallback)
        if not risk_counts and cnt:
            total_ded = cnt * 5
        health = max(0, 100 - total_ded)
        # status label
        if health >= 90:
            label = "healthy"
        elif health >= 70:
            label = "warning"
        else:
            label = "critical"
        return health, cnt, label

    auth_health, auth_cnt, auth_label = await score(["failed_login"])
    api_health, api_cnt, api_label = await score(["rate_limit", "url_blocked", "ssrf_blocked"])
    perm_health, perm_cnt, perm_label = await score(["permission_denied"])
    iso_health, iso_cnt, iso_label = await score(["data_isolation_violation", "prompt_injection"])

    overall = int((auth_health + api_health + perm_health + iso_health) / 4)

    # recent blocked counts
    recent_blocked = await db.execute(
        select(func.count()).select_from(SecurityEvent).where(
            SecurityEvent.created_at >= since, SecurityEvent.blocked == True
        )
    )
    blocked_24h = recent_blocked.scalar() or 0

    # total events 7d for trend
    week_ago = now - timedelta(days=7)
    week_total = await db.execute(
        select(func.count()).select_from(SecurityEvent).where(SecurityEvent.created_at >= week_ago)
    )
    week_cnt = week_total.scalar() or 0

    return {
        "overall_score": overall,
        "overall_status": "healthy" if overall >= 80 else "warning" if overall >= 60 else "critical",
        "dimensions": {
            "authentication": {"score": auth_health, "events_24h": auth_cnt, "status": auth_label},
            "api": {"score": api_health, "events_24h": api_cnt, "status": api_label},
            "agent_permissions": {"score": perm_health, "events_24h": perm_cnt, "status": perm_label},
            "data_isolation": {"score": iso_health, "events_24h": iso_cnt, "status": iso_label},
        },
        "blocked_24h": blocked_24h,
        "total_7d": week_cnt,
        "generated_at": now.isoformat(),
    }
