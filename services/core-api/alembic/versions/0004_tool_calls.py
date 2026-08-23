"""tool_calls audit table (blueprint §8 tool system, §25 sanitized logs)

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tool_calls",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("tool_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("input", sa.JSON(), nullable=False),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(op.f("ix_tool_calls_user_id"), "tool_calls", ["user_id"])
    op.create_index(op.f("ix_tool_calls_tool_id"), "tool_calls", ["tool_id"])
    op.create_index("ix_tool_calls_user_created", "tool_calls", ["user_id", "created_at"])
    op.create_index("ix_tool_calls_agent_created", "tool_calls", ["agent_id", "created_at"])


def downgrade() -> None:
    op.drop_table("tool_calls")
