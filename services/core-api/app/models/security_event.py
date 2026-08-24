import uuid

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UuidPkMixin

# Risk levels §53 trust levels
RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_CRITICAL = "critical"

# Event types §26 Security Center
EVENT_PROMPT_INJECTION = "prompt_injection"
EVENT_URL_BLOCKED = "url_blocked"
EVENT_SSRRF = "ssrf_blocked"
EVENT_RATE_LIMIT = "rate_limit"
EVENT_FAILED_LOGIN = "failed_login"
EVENT_SENSITIVE_DATA = "sensitive_data"
EVENT_PERMISSION_DENIED = "permission_denied"
EVENT_DATA_ISOLATION = "data_isolation_violation"


class SecurityEvent(Base, TimestampMixin, UuidPkMixin):
    """Blueprint §26 security_events: blocked attacks, violations, sensitive data.

    Powers the Security Center dashboard: Authentication/API/Agent-Permissions/
    Data-Isolation health + recent events + rolling score (§26, §53).
    """

    __tablename__ = "security_events"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, default=RISK_MEDIUM)
    blocked: Mapped[bool] = mapped_column(nullable=False, default=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    __table_args__ = (
        Index("ix_security_events_created", "created_at"),
        Index("ix_security_events_type_created", "event_type", "created_at"),
    )


class AuditLog(Base, TimestampMixin, UuidPkMixin):
    """General audit trail for auth, data access, admin actions (§25, §26)."""

    __tablename__ = "audit_logs"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    __table_args__ = (
        Index("ix_audit_logs_user_created", "user_id", "created_at"),
        Index("ix_audit_logs_action_created", "action", "created_at"),
    )
