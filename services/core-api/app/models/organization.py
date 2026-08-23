from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPkMixin


class Organization(Base, TimestampMixin, UuidPkMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    plan: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="free"
    )

    users: Mapped[list["User"]] = relationship(  # noqa: F821
        back_populates="org",
        passive_deletes=True,
    )
