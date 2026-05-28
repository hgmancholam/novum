"""Event type definitions as Pydantic discriminated union.

All events have:
- ``type``: discriminator field tied to :class:`EventType`
- ``model_config`` with ``extra="allow"`` for schema evolution (RF-03)
"""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import (
    AnswerKind,
    AuthorityTier,
    ComplexityHint,
    EventType,
    EvidencePolarity,
    Lane,
    QuestionType,
    SourceType,
    StopReason,
    TemporalSensitivity,
)
from app.domain.hypothesis import Hypothesis
from app.domain.structured import StructuredAnswerData


class BaseEvent(BaseModel):
    """Base class for all events."""

    model_config = ConfigDict(extra="allow")

    id: UUID | None = None
    run_id: UUID | None = None
    step_index: int | None = None
    parent_event_id: UUID | None = None
    created_at: datetime | None = None


# =============================================================================
# Question & Planning Events
# =============================================================================


class QuestionAskedEvent(BaseEvent):
    """Initial question submitted by user."""

    type: Literal[EventType.QUESTION_ASKED] = EventType.QUESTION_ASKED
    question: str
    user_context: str | None = None
    detected_question_type: QuestionType | None = None


class QuestionNormalizedEvent(BaseEvent):
    """Grammar/typo normalization of the user's question.

    Emitted right after :class:`QuestionAskedEvent` and before the classifier
    so the UI can show immediate feedback (“Buscando información sobre…”)
    even when the original input had typos or informal phrasing. Downstream
    LLM steps use ``normalized_question`` instead of the raw input.
    """

    type: Literal[EventType.QUESTION_NORMALIZED] = EventType.QUESTION_NORMALIZED
    original_question: str
    normalized_question: str
    was_corrected: bool
    language: str

class QuestionClassifiedEvent(BaseEvent):
    """Question classified with type and complexity hint (BRD-22).

    Emitted after normalization and classifier LLM call. Optional fields
    (``complexity_hint``, ``heuristic_signals``) are additive per RF-03;
    pre-BRD-22 events lack them and replay tolerates absence.
    """

    type: Literal[EventType.QUESTION_CLASSIFIED] = EventType.QUESTION_CLASSIFIED
    question_type: QuestionType
    classifier_confidence: float
    complexity_hint: ComplexityHint | None = None
    heuristic_signals: dict[str, Any] | None = None
    temporal_sensitivity: TemporalSensitivity | None = None  # BRD-23 WP-1

class SubClaim(BaseModel):
    """A sub-claim in the research plan."""

    model_config = ConfigDict(extra="allow")

    id: str
    text: str
    status: Literal["pending", "covered", "uncoverable"] = "pending"


class PlanCreatedEvent(BaseEvent):
    """Initial plan with sub-claims decomposition."""

    type: Literal[EventType.PLAN_CREATED] = EventType.PLAN_CREATED
    sub_claims: list[SubClaim]
    rationale: str
    complexity_hint: ComplexityHint | None = None  # BRD-22 (mirrored from classifier)
    expected_experts: list[str] | None = None  # BRD-22 (planner-emitted)
    preferred_sources: list[str] | None = None  # BRD-22 (e.g. ["wikipedia"] for trivial-factual)
    temporal_sensitivity: TemporalSensitivity | None = None  # BRD-23 WP-1 (mirrored)


class PlanCritiquedEvent(BaseEvent):
    """Plan critic evaluation (RF-14)."""

    type: Literal[EventType.PLAN_CRITIQUED] = EventType.PLAN_CRITIQUED
    critique: str
    issues: list[str]
    suggested_changes: list[str]
    acceptable: bool


class PlanRevisedEvent(BaseEvent):
    """Plan updated after critique."""

    type: Literal[EventType.PLAN_REVISED] = EventType.PLAN_REVISED
    previous_sub_claims: list[SubClaim]
    new_sub_claims: list[SubClaim]
    revision_rationale: str
    attempt_number: int  # 1 or 2 (max 2 per RF-14)
    complexity_hint: ComplexityHint | None = None  # BRD-22 (replay tolerates absence)


class HypothesesGeneratedEvent(BaseEvent):
    """Abductive hypotheses generated for causal/scenario questions (IP-25 Phase D)."""

    type: Literal[EventType.HYPOTHESES_GENERATED] = EventType.HYPOTHESES_GENERATED
    hypotheses: list[Hypothesis]


# =============================================================================
# Search & Evidence Events
# =============================================================================


class ToolCalledEvent(BaseEvent):
    """Search tool invocation."""

    type: Literal[EventType.TOOL_CALLED] = EventType.TOOL_CALLED
    source_type: SourceType
    query: str
    query_intent: str
    target_claim_id: str | None = None
    query_length_tokens: int | None = None  # BRD-23 WP-4 (observability)
    tavily_days_filter: int | None = None  # BRD-23 WP-1 (temporal routing)


class SourceResult(BaseModel):
    """A single result from a source."""

    model_config = ConfigDict(extra="allow")

    url: str
    title: str
    snippet: str
    relevance_score: float | None = None


class EvidenceAddedEvent(BaseEvent):
    """Evidence collected from a source."""

    type: Literal[EventType.EVIDENCE_ADDED] = EventType.EVIDENCE_ADDED
    source_type: SourceType
    source_url: str
    source_title: str
    extracted_text: str
    polarity: EvidencePolarity
    target_claim_id: str
    confidence: float
    source_published_date: datetime | None = None  # BRD-23 WP-1 (stale-citation judge input)
    authority_tier: AuthorityTier | None = None  # BRD-23 WP-3 (authority multiplier)


class ClaimCoveredEvent(BaseEvent):
    """Sub-claim has sufficient evidence."""

    type: Literal[EventType.CLAIM_COVERED] = EventType.CLAIM_COVERED
    claim_id: str
    claim_text: str
    evidence_ids: list[UUID]
    coverage_rationale: str


class ClaimUncoverableEvent(BaseEvent):
    """Sub-claim cannot be answered with available sources."""

    type: Literal[EventType.CLAIM_UNCOVERABLE] = EventType.CLAIM_UNCOVERABLE
    claim_id: str
    claim_text: str
    reason: str
    attempted_sources: list[SourceType]


class SourceFailedEvent(BaseEvent):
    """Source plugin returned an error."""

    type: Literal[EventType.SOURCE_FAILED] = EventType.SOURCE_FAILED
    source_type: SourceType
    query: str
    error_message: str
    recoverable: bool


class DeepFetchPerformedEvent(BaseEvent):
    """Full-content fetch performed for a shallow citation (BRD-23 WP-2).

    Emitted after the judge flags a claim as ``supported_but_shallow``.
    Informational: the underlying evidence row may be updated with the
    extracted full text. Replay tolerates absence (pre-WP-2 traces lack
    this event entirely).
    """

    type: Literal[EventType.DEEP_FETCH_PERFORMED] = EventType.DEEP_FETCH_PERFORMED
    source_type: SourceType
    url: str
    triggered_by_claim_id: str
    fetch_ms: int
    content_length: int
    success: bool
    failure_reason: str | None = None


class QueryReformulatedEvent(BaseEvent):
    """Query reformulation triggered by low relevance scores (IP-25 Phase 0).

    Emitted when all search results for a claim have relevance_score < 0.3.
    The search task performs ONE reformulated retry per claim per round.
    """

    type: Literal[EventType.QUERY_REFORMULATED] = EventType.QUERY_REFORMULATED
    original_query: str
    reformulated_query: str
    target_claim_id: str
    reason: Literal["low_relevance"]


class EchoChamberDetectedEvent(BaseEvent):
    """Echo chamber penalty applied (IP-25 Phase 0).

    Emitted when N ≥ 3 evidence items for the same claim:
    - All have non-null source_published_date
    - All fall within a window of < 7 days
    - C_agreement == 1.0 for that claim

    The diversity score is penalized by multiplying by 0.85.
    """

    type: Literal[EventType.ECHO_CHAMBER_DETECTED] = EventType.ECHO_CHAMBER_DETECTED
    target_claim_id: str
    n_sources: int
    date_window_days: int
    diversity_penalty_applied: float  # = 0.15


class RouteSelectedEvent(BaseEvent):
    """Lane routing decision (IP-25 Phase A).

    Emitted after QuestionClassified and before PlanCreated. Pure telemetry
    in Phase A — the pipeline continues through STANDARD flow regardless of
    the selected lane. Phases B-F will implement actual branching.
    """

    type: Literal[EventType.ROUTE_SELECTED] = EventType.ROUTE_SELECTED
    lane: Lane
    reason: str
    question_type: QuestionType
    complexity_hint: ComplexityHint
    temporal_sensitivity: TemporalSensitivity | None = None


class PlanGapsDetectedEvent(BaseEvent):
    """Dynamic re-decomposition triggered (IP-25 Phase B).

    Emitted after ANALYZING when structural confidence is below threshold
    and redecomposition_count < max_redecomposition. The gaps are LLM-
    identified angles not covered by the current plan.
    """

    type: Literal[EventType.PLAN_GAPS_DETECTED] = EventType.PLAN_GAPS_DETECTED
    gaps: list[str]
    extra_sub_claim_ids: list[str]  # New SubClaim IDs added to state


class NoProgressDetectedEvent(BaseEvent):
    """Confidence plateau detected (IP-25 Phase B).

    Emitted when confidence has not improved by at least 0.05 over the
    last 3 judge rounds. Forces transition to SYNTHESIZING to avoid
    wasted search cycles.
    """

    type: Literal[EventType.NO_PROGRESS_DETECTED] = EventType.NO_PROGRESS_DETECTED
    delta_3rounds: float
    current_confidence: float


class LaneEscalatedEvent(BaseEvent):
    """Lane escalation (IP-25 Phase C).

    Emitted when a lane (e.g., FAST) cannot satisfy its success criteria
    and escalates to a deeper lane (e.g., STANDARD). The run continues
    with the target lane's pipeline.
    """

    type: Literal[EventType.LANE_ESCALATED] = EventType.LANE_ESCALATED
    from_lane: Lane = Field(..., description="Source lane that escalated")
    to_lane: Lane = Field(..., description="Target lane for continuation")
    reason: str = Field(..., description="Why escalation occurred (e.g., 'mini_judge_rejected_or_low_S')")


# =============================================================================
# IP-25 Phase E: ReAct Loop Events
# =============================================================================


class AgentThoughtEvent(BaseEvent):
    """Agent reasoning thought in ReAct loop (IP-25 Phase E)."""

    type: Literal[EventType.AGENT_THOUGHT] = EventType.AGENT_THOUGHT
    step: int
    thought: str


class AgentActionEvent(BaseEvent):
    """Agent action selection in ReAct loop (IP-25 Phase E)."""

    type: Literal[EventType.AGENT_ACTION] = EventType.AGENT_ACTION
    step: int
    action_type: str  # "search" | "deep_fetch" | "evaluate_hypothesis" | "finish"
    args: dict[str, Any]


class AgentObservationEvent(BaseEvent):
    """Agent observation result in ReAct loop (IP-25 Phase E)."""

    type: Literal[EventType.AGENT_OBSERVATION] = EventType.AGENT_OBSERVATION
    step: int
    result_summary: str
    tokens: int


class HypothesisEvaluatedEvent(BaseEvent):
    """Hypothesis verdict updated (IP-25 Phase E)."""

    type: Literal[EventType.HYPOTHESIS_EVALUATED] = EventType.HYPOTHESIS_EVALUATED
    hypothesis_id: UUID
    verdict: str  # "confirmed" | "refuted"
    evidence_ids: list[UUID]


class HistorySummarizedEvent(BaseEvent):
    """ReAct history summarized to prevent token overflow (IP-25 Phase E)."""

    type: Literal[EventType.HISTORY_SUMMARIZED] = EventType.HISTORY_SUMMARIZED
    steps_summarized: int
    summary_tokens: int


class VerificationQuestionsGeneratedEvent(BaseEvent):
    """Verification questions generated for CoVe (IP-25 Phase F)."""

    type: Literal[EventType.VERIFICATION_QUESTIONS_GENERATED] = (
        EventType.VERIFICATION_QUESTIONS_GENERATED
    )
    questions: list[str]


class CoveContradictionDetectedEvent(BaseEvent):
    """CoVe detected a contradiction in the draft answer (IP-25 Phase F)."""

    type: Literal[EventType.COVE_CONTRADICTION_DETECTED] = (
        EventType.COVE_CONTRADICTION_DETECTED
    )
    question: str
    contradicting_evidence: str


# =============================================================================
# Detection Events (RF-04)
# =============================================================================


class AmbiguityDetectedEvent(BaseEvent):
    """Question ambiguity detected (RF-04)."""

    type: Literal[EventType.AMBIGUITY_DETECTED] = EventType.AMBIGUITY_DETECTED
    ambiguous_phrase: str
    possible_interpretations: list[str]
    clarification_needed: str
    dimensions: list[str] | None = None  # WP-2 additive for G9


class ContradictionSource(BaseModel):
    """A source involved in a contradiction."""

    model_config = ConfigDict(extra="allow")

    url: str
    title: str
    claim: str


class ContradictionDetectedEvent(BaseEvent):
    """Irreconcilable source conflict (RF-04).

    WP-2.5 additions (optional, additive): claim, supporting_chunk_ids,
    contradicting_chunk_ids, round.
    """

    type: Literal[EventType.CONTRADICTION_DETECTED] = EventType.CONTRADICTION_DETECTED
    claim_id: str
    source_a: ContradictionSource
    source_b: ContradictionSource
    nature_of_conflict: str

    # WP-2.5 additions (all optional for backward compat)
    claim: str | None = None
    supporting_chunk_ids: list[str] | None = None
    contradicting_chunk_ids: list[str] | None = None
    round: int | None = None


class ContradictionResolvedEvent(BaseEvent):
    """Contradiction resolved through additional evidence."""

    type: Literal[EventType.CONTRADICTION_RESOLVED] = EventType.CONTRADICTION_RESOLVED
    original_contradiction_id: UUID
    resolution: str
    winning_source: str | None = None
    rationale: str


class UserContextChallengedEvent(BaseEvent):
    """User context contradicts evidence (RF-07)."""

    type: Literal[EventType.USER_CONTEXT_CHALLENGED] = EventType.USER_CONTEXT_CHALLENGED
    user_context_claim: str
    contradicting_evidence: str
    source_url: str


class PriorRunHintReplayedEvent(BaseEvent):
    """Instant-answer cache replay (BRD-22).

    Emitted when the orchestrator short-circuits a new run by reusing a
    prior high-confidence result. The new run skips classify/plan/search
    and emits synthetic ``JudgeRuledEvent`` + ``StoppedEvent`` carrying
    the prior answer payload.
    """

    type: Literal[EventType.PRIOR_RUN_HINT_REPLAYED] = EventType.PRIOR_RUN_HINT_REPLAYED
    source_run_id: UUID
    source_final_confidence: float
    source_stop_reason: StopReason
    source_answer_kind: AnswerKind | None = None
    normalised_question: str
    prior_completed_at: datetime


# =============================================================================
# Judge & Confidence Events (RF-12, RF-15, WP-5)
# =============================================================================


class DraftSynthesizedEvent(BaseEvent):
    """Final draft emitted by the synthesizer (PR-3 Mejora 3.2, RF-03).

    Emitted after every successful synthesis (STANDARD/DEEP/CoVe) so the
    event log captures the draft + ``answer_kind`` independently of the
    eventual ``JudgeRuled``/``Stopped`` events. Without this the FAST lane
    and budget-stopped DEEP runs reach ``Stopped`` with no audit trail of
    the draft itself.
    """

    type: Literal[EventType.DRAFT_SYNTHESIZED] = EventType.DRAFT_SYNTHESIZED
    prose: str
    answer_kind: AnswerKind | None = None
    citation_count: int = 0
    key_point_count: int = 0
    source: Literal["standard", "deep_react", "deep_cove", "fast"] = "standard"


class JudgeRuledEvent(BaseEvent):
    """Judge LLM evaluation (RF-12, WP-3 G5 C_kind_appropriateness, WP-5 extensions)."""

    type: Literal[EventType.JUDGE_RULED] = EventType.JUDGE_RULED
    judge_model: str
    judge_confidence: float
    structural_confidence: float
    final_confidence: float
    threshold: float
    passed: bool
    rationale: str
    suggested_improvements: list[str] | None = None
    answer_kind: AnswerKind | None = None  # RF-17 (required when passed=True per WP-3)
    kind_appropriateness: float = 1.0  # WP-3 G5: judge-scored 0..1 "does kind fit question?"

    # WP-5 extensions (all optional for backward compat)
    coherence: float | None = None  # 0..1 logical consistency score
    contradictions_detected: list[str] | None = None  # specific contradictions judge found
    missing_evidence: list[str] | None = None  # gaps judge identified


class ConfidenceMismatchEvent(BaseEvent):
    """S and J diverge significantly (RF-15)."""

    type: Literal[EventType.CONFIDENCE_MISMATCH] = EventType.CONFIDENCE_MISMATCH
    structural_confidence: float
    judge_confidence: float
    divergence: float
    trust_flag: str


# =============================================================================
# WP-4: Saturation Detection
# =============================================================================


class SaturationDetectedEvent(BaseEvent):
    """Novelty-based saturation signal fired (WP-4).

    Computed as: novelty = 1 - mean(max_cosine_similarity(chunk_i, prior_corpus))
    over the last k=3 chunks from the current round.
    """

    type: Literal[EventType.SATURATION_DETECTED] = EventType.SATURATION_DETECTED
    round_index: int
    novelty: float  # 0..1, lower means more repetitive
    k: int = 3  # window size (last k chunks)
    threshold: float  # NOVELTY_FLOOR from config


# =============================================================================
# WP-5: Judge Provider Degradation
# =============================================================================


class JudgeProviderDegradedEvent(BaseEvent):
    """Judge provider failed, fell back to alternate provider (WP-5)."""

    type: Literal[EventType.JUDGE_PROVIDER_DEGRADED] = EventType.JUDGE_PROVIDER_DEGRADED
    requested_provider: str  # e.g. "anthropic"
    fallback_provider: str  # e.g. "github"
    error_class: str  # exception class name


# =============================================================================
# Error & Recovery Events (RF-11)
# =============================================================================


class AgentErroredEvent(BaseEvent):
    """Unrecoverable error during execution."""

    type: Literal[EventType.AGENT_ERRORED] = EventType.AGENT_ERRORED
    error_type: str
    error_message: str
    stack_trace: str | None = None
    recoverable: bool
    recovery_suggestion: str | None = None
    # Structured tag for UI differentiation. ``llm_pool_rate_limited``
    # signals that all PATs in the GitHub Models rotation pool returned
    # 429 simultaneously; the frontend shows a "rate-limit" modal
    # instead of a generic failure dialog.
    error_code: str | None = None


class ResumedAfterErrorEvent(BaseEvent):
    """Run resumed after an error."""

    type: Literal[EventType.RESUMED_AFTER_ERROR] = EventType.RESUMED_AFTER_ERROR
    original_error_event_id: UUID
    resume_point: str


class ResumedAfterCancelEvent(BaseEvent):
    """Run resumed after user cancellation."""

    type: Literal[EventType.RESUMED_AFTER_CANCEL] = EventType.RESUMED_AFTER_CANCEL
    cancel_event_id: UUID
    resume_point: str


# =============================================================================
# Terminal Event
# =============================================================================


class StopRationale(BaseModel):
    """Structured 'why we stopped' payload (RF-13 / RF-19, WP-3 G2).

    Aggregates the four signals the challenge spec expects to see on a
    terminal run: evidence quality, source agreement, novelty (information
    gain), and final confidence — plus the ceiling actually applied and a
    short human-readable summary from the judge.
    """

    model_config = ConfigDict(extra="allow")

    reason: StopReason
    triggering_signal: str  # e.g. "judge", "budget", "early_stop"
    summary: str  # <= 280 chars, human-readable
    confidence: float | None = None
    # PR-1 Mejora 2.2: discriminator so the UI can render "Confianza estructural
    # 0.58 · juez no confirmado" instead of treating a null judge confidence as
    # 0 %. Set to ``"judge"`` when ``confidence`` is the judge score, to
    # ``"structural"`` when it falls back to the structural score S.
    confidence_kind: Literal["judge", "structural"] | None = None


class AnswerSection(BaseModel):
    """Section of a structured answer."""

    model_config = ConfigDict(extra="allow")

    heading: str
    content: str


class Citation(BaseModel):
    """Citation reference in the answer."""

    model_config = ConfigDict(extra="allow")

    id: int
    url: str
    title: str


class StoppedEvent(BaseEvent):
    """Terminal event with final answer or budget/error stop."""

    type: Literal[EventType.STOPPED] = EventType.STOPPED
    stop_reason: StopReason

    # Answer (if judge_confirmed)
    answer_prose: str | None = None
    answer_structured: str | None = None  # pre-rendered structured format (BRD-16 enhancement)
    answer_structured_data: StructuredAnswerData | None = None  # JSON structured payload (RF-10)
    answer_sections: list[AnswerSection] | None = None
    citations: list[Citation] | None = None
    answer_kind: AnswerKind | None = None  # RF-17 (required for judge_confirmed per WP-3)

    # WP-3 G2: structured stop rationale
    stop_rationale: StopRationale | None = None

    # Metrics
    total_tokens: int | None = None
    total_duration_seconds: float | None = None


# =============================================================================
# Discriminated Union
# =============================================================================


Event = Annotated[
    QuestionAskedEvent | QuestionNormalizedEvent | QuestionClassifiedEvent | PlanCreatedEvent | PlanCritiquedEvent | PlanRevisedEvent | HypothesesGeneratedEvent | ToolCalledEvent | EvidenceAddedEvent | ClaimCoveredEvent | ClaimUncoverableEvent | SourceFailedEvent | DeepFetchPerformedEvent | QueryReformulatedEvent | EchoChamberDetectedEvent | RouteSelectedEvent | PlanGapsDetectedEvent | NoProgressDetectedEvent | LaneEscalatedEvent | AgentThoughtEvent | AgentActionEvent | AgentObservationEvent | HypothesisEvaluatedEvent | HistorySummarizedEvent | VerificationQuestionsGeneratedEvent | CoveContradictionDetectedEvent | AmbiguityDetectedEvent | ContradictionDetectedEvent | ContradictionResolvedEvent | UserContextChallengedEvent | PriorRunHintReplayedEvent | DraftSynthesizedEvent | JudgeRuledEvent | ConfidenceMismatchEvent | SaturationDetectedEvent | JudgeProviderDegradedEvent | AgentErroredEvent | ResumedAfterErrorEvent | ResumedAfterCancelEvent | StoppedEvent,
    Field(discriminator="type"),
]


# Mapping for deserialization and FSM dispatch.
EVENT_TYPE_MAP: dict[str, type[BaseEvent]] = {
    EventType.QUESTION_ASKED: QuestionAskedEvent,
    EventType.QUESTION_NORMALIZED: QuestionNormalizedEvent,
    EventType.QUESTION_CLASSIFIED: QuestionClassifiedEvent,
    EventType.PLAN_CREATED: PlanCreatedEvent,
    EventType.PLAN_CRITIQUED: PlanCritiquedEvent,
    EventType.PLAN_REVISED: PlanRevisedEvent,
    EventType.HYPOTHESES_GENERATED: HypothesesGeneratedEvent,
    EventType.TOOL_CALLED: ToolCalledEvent,
    EventType.EVIDENCE_ADDED: EvidenceAddedEvent,
    EventType.CLAIM_COVERED: ClaimCoveredEvent,
    EventType.CLAIM_UNCOVERABLE: ClaimUncoverableEvent,
    EventType.SOURCE_FAILED: SourceFailedEvent,
    EventType.DEEP_FETCH_PERFORMED: DeepFetchPerformedEvent,
    EventType.QUERY_REFORMULATED: QueryReformulatedEvent,
    EventType.ECHO_CHAMBER_DETECTED: EchoChamberDetectedEvent,
    EventType.ROUTE_SELECTED: RouteSelectedEvent,
    EventType.PLAN_GAPS_DETECTED: PlanGapsDetectedEvent,
    EventType.NO_PROGRESS_DETECTED: NoProgressDetectedEvent,
    EventType.LANE_ESCALATED: LaneEscalatedEvent,
    EventType.AGENT_THOUGHT: AgentThoughtEvent,
    EventType.AGENT_ACTION: AgentActionEvent,
    EventType.AGENT_OBSERVATION: AgentObservationEvent,
    EventType.HYPOTHESIS_EVALUATED: HypothesisEvaluatedEvent,
    EventType.HISTORY_SUMMARIZED: HistorySummarizedEvent,
    EventType.VERIFICATION_QUESTIONS_GENERATED: VerificationQuestionsGeneratedEvent,
    EventType.COVE_CONTRADICTION_DETECTED: CoveContradictionDetectedEvent,
    EventType.AMBIGUITY_DETECTED: AmbiguityDetectedEvent,
    EventType.CONTRADICTION_DETECTED: ContradictionDetectedEvent,
    EventType.CONTRADICTION_RESOLVED: ContradictionResolvedEvent,
    EventType.USER_CONTEXT_CHALLENGED: UserContextChallengedEvent,
    EventType.PRIOR_RUN_HINT_REPLAYED: PriorRunHintReplayedEvent,
    EventType.DRAFT_SYNTHESIZED: DraftSynthesizedEvent,
    EventType.JUDGE_RULED: JudgeRuledEvent,
    EventType.CONFIDENCE_MISMATCH: ConfidenceMismatchEvent,
    EventType.SATURATION_DETECTED: SaturationDetectedEvent,
    EventType.JUDGE_PROVIDER_DEGRADED: JudgeProviderDegradedEvent,
    EventType.AGENT_ERRORED: AgentErroredEvent,
    EventType.RESUMED_AFTER_ERROR: ResumedAfterErrorEvent,
    EventType.RESUMED_AFTER_CANCEL: ResumedAfterCancelEvent,
    EventType.STOPPED: StoppedEvent,
}


# Forkable events (RF-03): decision points a user can branch from.
FORKABLE_EVENTS: set[EventType] = {
    EventType.PLAN_CREATED,
    EventType.AMBIGUITY_DETECTED,
    EventType.CONTRADICTION_DETECTED,
    EventType.JUDGE_RULED,
    EventType.STOPPED,
}
