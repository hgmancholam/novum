"""Run ORM model for research run tracking."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import TIMESTAMP, Float, ForeignKey, String, Text, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.event import Event


# Enum types matching the database. `create_type=False` because the enums
# are created explicitly by the Alembic migration, not by the ORM.
StopReasonType = ENUM(
    "judge_confirmed",
    "honest_unanswerable",
    "honest_contradiction",
    "honest_ambiguous",
    "stopped_by_budget",
    "user_cancelled",
    "errored",
    name="stop_reason",
    create_type=False,
)

QuestionTypeEnum = ENUM(
    "factual",
    "comparative",
    "definitional",
    "state_of_art",
    "causal",
    name="question_type",
    create_type=False,
)

OutputFormatEnum = ENUM(
    "prose",
    "structured",
    name="output_format",
    create_type=False,
)


class Run(Base):
    """Research run with question, configuration, and terminal state."""

    __tablename__ = "runs"

    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # Owner reference (RF-05)
    owner_username: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("users.username", ondelete="CASCADE"),
        nullable=False,
    )

    # Question
    question: Mapped[str] = mapped_column(Text, nullable=False)
    user_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_type: Mapped[str | None] = mapped_column(QuestionTypeEnum, nullable=True)

    # Configuration
    output_format: Mapped[str] = mapped_column(
        OutputFormatEnum,
        nullable=False,
        server_default=text("'prose'"),
    )
    confidence_threshold: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        server_default=text("0.7"),
    )

    # Timing
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    stopped_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    # Terminal state (RF-01)
    stop_reason: Mapped[str | None] = mapped_column(StopReasonType, nullable=True)

    # Forking (RF-03)
    parent_run_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    forked_at_event_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    events: Mapped[list["Event"]] = relationship(
        "Event",
        back_populates="run",
        order_by="Event.step_index",
        cascade="all, delete-orphan",
        foreign_keys="Event.run_id",
    )
