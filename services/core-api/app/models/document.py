import uuid

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UuidPkMixin

STATUS_UPLOADED = "uploaded"
STATUS_FAILED = "failed"


class Document(Base, TimestampMixin, UuidPkMixin):
    """A user-uploaded file (MVP: PDF only — blueprint §11 PDF Agent,
    §25 upload validation). Stored under a randomized name outside any
    web-servable root; ownership is the isolation boundary every tool
    must re-check before reading.
    """

    __tablename__ = "documents"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(128), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=STATUS_UPLOADED
    )

    __table_args__ = (
        Index("ix_documents_user_created", "user_id", "created_at"),
    )
