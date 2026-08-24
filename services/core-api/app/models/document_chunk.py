import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UuidPkMixin


class DocumentChunk(Base, TimestampMixin, UuidPkMixin):
    """Blueprint §13 RAG: one chunk of a user's document plus its
    embedding. Every row carries user_id so vector search can be scoped
    (§16) — the same isolation rule as documents.
    """

    __tablename__ = "document_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=False)

    __table_args__ = (
        Index("ix_chunks_doc_idx", "document_id", "chunk_index", unique=True),
        Index("ix_chunks_user_created", "user_id", "created_at"),
    )
