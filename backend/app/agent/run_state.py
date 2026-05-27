"""RunState — mutable in-memory state for an executing research agent.

Events are the immutable record of truth (RF-03); this model is
ephemeral working memory. Schema evolution uses ``extra="allow"``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.agent.states import AgentState, can_transition
from app.domain.enums import AnswerKind, EventType, QuestionType, StopReason
from app.domain.events import (
    AnswerSection,
    BaseEvent,
    ContradictionDetectedEvent,
    SubClaim,
)


class EvidenceItem(BaseModel):
    """In-memory evidence linked to an emitted ``EvidenceAddedEvent``."""

    model_config = ConfigDict(extra="allow", frozen=False)

    event_id: UUID = Field(default_factory=uuid4)
    claim_id: str
    source_url: str
    source_title: str
    text: str
    polarity: str
    confidence: float = Field(ge=0.0, le=1.0)


class RunState(BaseModel):
    """Ephemeral mutable state for one agent run."""

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=False)

    run_id: UUID
    question: str
    user_context: str | None = None
    question_type: QuestionType | None = None

    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    output_format: str = "prose"

    # Set by a future ambiguity-detection task; read by HonestStopSignal (BRD-09).
    has_ambiguity: bool = False

    current_state: AgentState = AgentState.INIT
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    sub_claims: list[SubClaim] = Field(default_factory=list)
    plan_revision_count: int = 0
    max_plan_revisions: int = 2

    evidence: list[EvidenceItem] = Field(default_factory=list)
    covered_claims: list[str] = Field(default_factory=list)
    uncoverable_claims: list[str] = Field(default_factory=list)
    contradictions: list[ContradictionDetectedEvent] = Field(default_factory=list)

    # ``max_searches`` is measured in rounds (one full call to the search
    # handler), not in individual tool calls (O-08).
    search_count: int = 0
    max_searches: int = 20
    failed_sources: list[str] = Field(default_factory=list)

    draft_answer: str | None = None
    draft_sections: list[AnswerSection] | None = None
    draft_citations: list[str] = Field(default_factory=list)

    judge_attempts: int = 0
    max_judge_attempts: int = 3
    last_judge_confidence: float | None = None
    last_structural_confidence: float | None = None
    last_coverage: float = 0.0  # WP-3 G8: for early-stop check
    last_agreement: float = 0.0  # WP-3 G8: for early-stop check

    stop_reason: StopReason | None = None
    final_answer: str | None = None

    # ``total_tokens`` is a best-effort lower bound (O-12).
    total_tokens: int = 0
    iteration_count: int = 0

    # WP-2 additions
    selected_answer_kind: AnswerKind | None = None
    ambiguity_dimensions: list[str] = Field(default_factory=list)

    # WP-2 helper — in-memory event list for has_event() lookups
    events: list[BaseEvent] = Field(default_factory=list)

    # WP-4: In-memory embeddings for saturation detection (never serialized)
    chunk_embeddings: dict[str, Any] = Field(default_factory=dict, exclude=True)
    last_novelty: float | None = None

    def transition_to(self, new_state: AgentState) -> None:
        if not can_transition(self.current_state, new_state):
            raise ValueError(f"Invalid transition: {self.current_state} -> {new_state}")
        self.current_state = new_state

    def add_evidence(self, item: EvidenceItem) -> None:
        self.evidence.append(item)

    def mark_claim_covered(self, claim_id: str) -> None:
        if claim_id not in self.covered_claims:
            self.covered_claims.append(claim_id)
        for c in self.sub_claims:
            if c.id == claim_id:
                c.status = "covered"

    def mark_claim_uncoverable(self, claim_id: str) -> None:
        if claim_id not in self.uncoverable_claims:
            self.uncoverable_claims.append(claim_id)
        for c in self.sub_claims:
            if c.id == claim_id:
                c.status = "uncoverable"

    def pending_claims(self) -> list[SubClaim]:
        return [c for c in self.sub_claims if c.status == "pending"]

    def all_claims_resolved(self) -> bool:
        return not self.pending_claims()

    def coverage_ratio(self) -> float:
        if not self.sub_claims:
            return 0.0
        return len(self.covered_claims) / len(self.sub_claims)

    def has_event(self, event_type: EventType) -> bool:
        """Check if an event of the given type exists in the run.

        WP-2 helper for G3/G10 wiring.
        """
        return any(e.type == event_type for e in self.events)
