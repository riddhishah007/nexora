"""Security Center: security_events + audit_logs (§26, §53)

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "security_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("agent_id", sa.String(length=64), nullable=True),
        sa.Column("risk_level", sa.String(length=16), nullable=False, server_default="medium"),
        sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("details", JSONB, nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_security_events_user_id", "security_events", ["user_id"])
    op.create_index(op.f("ix_security_events_event_type"), "security_events", ["event_type"])
    op.create_index("ix_security_events_created", "security_events", ["created_at"])
    op.create_index("ix_security_events_type_created", "security_events", ["event_type", "created_at"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource", sa.String(length=128), nullable=True),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column("details", JSONB, nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_user_created", "audit_logs", ["user_id", "created_at"])
    op.create_index("ix_audit_logs_action_created", "audit_logs", ["action", "created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("security_events")
