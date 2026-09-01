import uuid

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UuidPkMixin


class Project(Base, TimestampMixin, UuidPkMixin):
    """Tenant workspace — groups conversations/workflows/documents per user.

    MVP scope: per-user ownership (user_id + org_id), name, description.
    Full blueprint envisions cross-user teams via organizations — this
    keeps single-user isolation while satisfying §10 projects table.
    """

    __tablename__ = "projects"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="active"
    )

    __table_args__ = (
        Index("ix_projects_user_created", "user_id", "created_at"),
        Index("ix_projects_org_created", "org_id", "created_at"),
    )
