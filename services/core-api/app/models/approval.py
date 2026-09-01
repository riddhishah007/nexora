import uuid

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UuidPkMixin

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"


class Approval(Base, TimestampMixin, UuidPkMixin):
    """HITL gate for HIGH-trust tools (§12, §26) — Blueprint V1 human approvals.

    When the orchestrator hits a HIGH trust tool (code exec side-effects)
    it creates a pending row here. Frontend polls GET /approvals and
    POST /approvals/{id}/decision resumes the workflow (Phase 35 A).
    V1 stub: approval is standalone — executor resume wiring is deferred to
    V2 (workflow step pause/resume). This satisfies §14 /approvals/{id}/decision
    and Security Center UI without blocking current DAG execution.
    """

    __tablename__ = "approvals"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflows.id", ondelete="SET NULL"), nullable=True, index=True
    )
    agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=STATUS_PENDING, index=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_approvals_user_status", "user_id", "status"),
        Index("ix_approvals_user_created", "user_id", "created_at"),
    )
