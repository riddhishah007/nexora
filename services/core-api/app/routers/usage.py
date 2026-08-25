"""Phase 23 — Usage/metrics API over the api_usage table.

Per-user isolation: every aggregate is scoped to current_user.id.
Blueprint §"observability": tokens/calls/latency surfaced to the UI.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.api_usage import ApiUsage
from app.models.user import User

router = APIRouter(prefix="/usage", tags=["usage"])


class ModelUsage(BaseModel):
    provider: str
    model: str
    calls: int
    tokens_in: int
    tokens_out: int
    avg_latency_ms: float
    est_cost_usd: float


class DailyUsage(BaseModel):
    day: str  # YYYY-MM-DD
    calls: int
    tokens_in: int
    tokens_out: int


class UsageSummary(BaseModel):
    days: int
    total_calls: int
    cached_calls: int
    tokens_in: int
    tokens_out: int
    avg_latency_ms: float
    est_cost_usd: float
    by_model: list[ModelUsage]
    by_day: list[DailyUsage]


@router.get("/summary", response_model=UsageSummary)
async def usage_summary(
    days: int = Query(default=7, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsageSummary:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    scope = (ApiUsage.user_id == current_user.id) & (ApiUsage.created_at >= since)

    totals = (
        await db.execute(
            select(
                func.count().label("calls"),
                func.count(case((ApiUsage.cached.is_(True), 1))).label("cached"),
                func.coalesce(func.sum(ApiUsage.tokens_in), 0).label("tokens_in"),
                func.coalesce(func.sum(ApiUsage.tokens_out), 0).label("tokens_out"),
                func.coalesce(func.avg(ApiUsage.latency_ms), 0.0).label("avg_latency"),
                func.coalesce(func.sum(ApiUsage.estimated_cost), 0.0).label("est_cost"),
            ).where(scope)
        )
    ).one()

    model_rows = (
        await db.execute(
            select(
                ApiUsage.provider,
                ApiUsage.model,
                func.count().label("calls"),
                func.coalesce(func.sum(ApiUsage.tokens_in), 0).label("tokens_in"),
                func.coalesce(func.sum(ApiUsage.tokens_out), 0).label("tokens_out"),
                func.avg(ApiUsage.latency_ms).label("avg_latency"),
                func.coalesce(func.sum(ApiUsage.estimated_cost), 0.0).label("est_cost"),
            )
            .where(scope)
            .group_by(ApiUsage.provider, ApiUsage.model)
            .order_by(func.count().desc())
            .limit(25)
        )
    ).all()

    day_rows = (
        await db.execute(
            select(
                func.date(ApiUsage.created_at).label("day"),
                func.count().label("calls"),
                func.coalesce(func.sum(ApiUsage.tokens_in), 0).label("tokens_in"),
                func.coalesce(func.sum(ApiUsage.tokens_out), 0).label("tokens_out"),
            )
            .where(scope)
            .group_by(func.date(ApiUsage.created_at))
            .order_by(func.date(ApiUsage.created_at).asc())
        )
    ).all()

    total_calls = int(totals.calls or 0)
    return UsageSummary(
        days=days,
        total_calls=total_calls,
        cached_calls=int(totals.cached or 0),
        tokens_in=int(totals.tokens_in or 0),
        tokens_out=int(totals.tokens_out or 0),
        avg_latency_ms=round(float(totals.avg_latency or 0), 1),
        est_cost_usd=round(float(totals.est_cost or 0), 6),
        by_model=[
            ModelUsage(
                provider=r.provider,
                model=r.model,
                calls=int(r.calls),
                tokens_in=int(r.tokens_in),
                tokens_out=int(r.tokens_out),
                avg_latency_ms=round(float(r.avg_latency or 0), 1),
                est_cost_usd=round(float(r.est_cost or 0), 6),
            )
            for r in model_rows
        ],
        by_day=[
            DailyUsage(
                day=r.day.isoformat() if hasattr(r.day, "isoformat") else str(r.day),
                calls=int(r.calls),
                tokens_in=int(r.tokens_in),
                tokens_out=int(r.tokens_out),
            )
            for r in day_rows
        ],
    )
