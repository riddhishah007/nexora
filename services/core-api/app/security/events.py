"""Helpers to persist SecurityEvent / AuditLog (§26).

All helpers are best-effort: logging must never break the request.
Use `await log_security_event(...)` inside a try/except in callers, or
call the fire-and-forget wrapper that swallows errors.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security_event import AuditLog, SecurityEvent

async def log_security_event(
    db: AsyncSession,
    event_type: str,
    risk_level: str = "medium",
    blocked: bool = True,
    user_id: uuid.UUID | str | None = None,
    agent_id: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
    try:
        if isinstance(user_id, str):
            try:
                user_id = uuid.UUID(user_id)
            except ValueError:
                user_id = None
        row = SecurityEvent(
            user_id=user_id,
            event_type=event_type,
            agent_id=agent_id,
            risk_level=risk_level,
            blocked=blocked,
            details=details or {},
            ip_address=ip_address,
        )
        db.add(row)
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        # FK violation (fake user_id) -> retry with NULL
        msg = str(exc)
        if "violates foreign key" in msg.lower() and row.user_id is not None:  # type: ignore[has-type]
            try:
                await db.rollback()
                row.user_id = None  # type: ignore[attr-defined]
                db.add(row)
                await db.commit()
                return
            except Exception as e2:  # noqa: BLE001
                print(f"[security] log_security_event retry failed: {e2}")
                try:
                    await db.rollback()
                except Exception:
                    pass
                return
        print(f"[security] log_security_event failed: {exc}")
        try:
            await db.rollback()
        except Exception:
            pass

async def log_audit(
    db: AsyncSession,
    action: str,
    user_id: uuid.UUID | str | None = None,
    resource: str | None = None,
    resource_id: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
    try:
        if isinstance(user_id, str):
            try:
                user_id = uuid.UUID(user_id)
            except ValueError:
                user_id = None
        row = AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
        )
        db.add(row)
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if "violates foreign key" in msg.lower() and row.user_id is not None:  # type: ignore[has-type]
            try:
                await db.rollback()
                row.user_id = None  # type: ignore[attr-defined]
                db.add(row)
                await db.commit()
                return
            except Exception as e2:  # noqa: BLE001
                print(f"[security] log_audit retry failed: {e2}")
                try:
                    await db.rollback()
                except Exception:
                    pass
                return
        print(f"[security] log_audit failed: {exc}")
        try:
            await db.rollback()
        except Exception:
            pass
