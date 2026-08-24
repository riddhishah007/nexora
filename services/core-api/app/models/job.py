import uuid

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UuidPkMixin

JOB_QUEUED = "queued"
JOB_RUNNING = "running"
JOB_DONE = "done"
JOB_FAILED = "failed"
JOB_DEAD = "dead"  # after max retries

JOB_TYPE_RAG_INGEST = "rag_ingest"
JOB_TYPE_WORKFLOW = "workflow"
# future: pdf_process, etc.

class Job(Base, TimestampMixin, UuidPkMixin):
    """Background job for worker queue (§18).

    Simple persistent queue with idempotency_key (document_id+type) to avoid
    double-enqueue on retry. Payload/result are JSONB for flexibility.
    """

    __tablename__ = "jobs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=JOB_QUEUED, index=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    attempts: Mapped[int] = mapped_column(nullable=False, default=0)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=False)

    __table_args__ = (
        Index("ix_jobs_user_created", "user_id", "created_at"),
        Index("ix_jobs_type_status", "type", "status"),
        Index("ix_jobs_idem", "idempotency_key"),
    )
