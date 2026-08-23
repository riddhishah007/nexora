import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPkMixin

ROLE_USER = "user"
ROLE_ADMIN = "admin"


class User(Base, TimestampMixin, UuidPkMixin):
    __tablename__ = "users"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(
        String(320), unique=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    role: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=ROLE_USER
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    org: Mapped["Organization"] = relationship(  # noqa: F821
        back_populates="users",
    )
    sessions: Mapped[list["UserSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class UserSession(Base, TimestampMixin, UuidPkMixin):
    __tablename__ = "sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    refresh_token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="sessions")
