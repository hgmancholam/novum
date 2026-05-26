"""Event ORM model (RF-03: Append-only event log)."""

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import TIMESTAMP, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.run import Run


class Event(Base):
    """Append-only event in the run event log (RF-03)."""

    __tablename__ = "events"

    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # Run reference
    run_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Ordering within a run
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Lineage (for fork/resume visualization)
    parent_event_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Discriminator for the ~17 event types
    type: Mapped[str] = mapped_column(String(50), nullable=False)

    # JSONB payload; schema enforced by Pydantic, not the database
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    run: Mapped["Run"] = relationship(
        "Run",
        back_populates="events",
        foreign_keys=[run_id],
    )

    __table_args__ = (
        UniqueConstraint("run_id", "step_index", name="uq_run_step"),
    )
