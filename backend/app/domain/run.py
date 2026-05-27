"""Run state and request/response models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import OutputFormat, QuestionType, StopReason


class RunCreate(BaseModel):
    """Request body for creating a new run."""

    question: str = Field(..., min_length=10, max_length=2000)
    user_context: str | None = Field(None, max_length=1000)  # RF-07
    output_format: OutputFormat = OutputFormat.PROSE
    confidence_threshold: float = Field(0.7, ge=0.0, le=1.0)  # RF-12


class RunResponse(BaseModel):
    """Response model for a run."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_username: str
    question: str
    user_context: str | None
    question_type: QuestionType | None
    output_format: OutputFormat
    confidence_threshold: float
    started_at: datetime
    stopped_at: datetime | None
    stop_reason: StopReason | None
    parent_run_id: UUID | None
    forked_at_event_id: UUID | None


class RunListItem(BaseModel):
    """Lightweight run for list views (RF-09)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    question: str
    started_at: datetime
    stopped_at: datetime | None
    stop_reason: StopReason | None


class RunListPage(BaseModel):
    """Keyset-paginated page of run summaries (BRD-20 §4.4, RF-09)."""

    # extra="allow" honours the schema-evolution rule for envelopes that
    # may grow new optional metadata (BRD-20 schema-evolution constraint).
    model_config = ConfigDict(extra="allow")

    items: list[RunListItem]
    has_more: bool
    next_cursor: str | None = None


class RunForkRequest(BaseModel):
    """Request to fork a run from a specific event (RF-03)."""

    event_id: UUID
