"""Tests for event models and the discriminated union (BRD-02 §4.3).

Covers AC-01 (serialization), AC-02 (discriminated union), AC-03 (schema
evolution), AC-04 (count), and AC-05 (forkable set).
"""

import json
from uuid import uuid4

import pytest
from pydantic import TypeAdapter

from app.domain.enums import (
    EventType,
    EvidencePolarity,
    QuestionType,
    SourceType,
    StopReason,
)
from app.domain.events import (
    EVENT_TYPE_MAP,
    FORKABLE_EVENTS,
    AgentActionEvent,
    AgentErroredEvent,
    AgentObservationEvent,
    AgentThoughtEvent,
    AmbiguityDetectedEvent,
    AnswerSection,
    Citation,
    ClaimCoveredEvent,
    ClaimUncoverableEvent,
    ConfidenceMismatchEvent,
    ContradictionDetectedEvent,
    ContradictionResolvedEvent,
    ContradictionSource,
    CoveContradictionDetectedEvent,
    DeepFetchPerformedEvent,
    EchoChamberDetectedEvent,
    Event,
    EvidenceAddedEvent,
    HistorySummarizedEvent,
    HypothesesGeneratedEvent,
    HypothesisEvaluatedEvent,
    JudgeProviderDegradedEvent,
    JudgeRuledEvent,
    LaneEscalatedEvent,
    NoProgressDetectedEvent,
    PlanCreatedEvent,
    PlanCritiquedEvent,
    PlanGapsDetectedEvent,
    PlanRevisedEvent,
    PriorRunHintReplayedEvent,
    QueryReformulatedEvent,
    QuestionAskedEvent,
    QuestionClassifiedEvent,
    QuestionNormalizedEvent,
    ResumedAfterCancelEvent,
    ResumedAfterErrorEvent,
    RouteSelectedEvent,
    SaturationDetectedEvent,
    SourceFailedEvent,
    StoppedEvent,
    SubClaim,
    ToolCalledEvent,
    UserContextChallengedEvent,
    VerificationQuestionsGeneratedEvent,
)

_EVENT_ADAPTER: TypeAdapter[Event] = TypeAdapter(Event)


# ---------------------------------------------------------------------------
# AC-01: Serialization
# ---------------------------------------------------------------------------


def test_stopped_event_serializes_all_fields() -> None:
    """AC-01: ``StoppedEvent`` round-trips through ``model_dump_json``."""
    event = StoppedEvent(
        id=uuid4(),
        run_id=uuid4(),
        step_index=42,
        stop_reason=StopReason.JUDGE_CONFIRMED,
        answer_prose="The answer.",
        answer_sections=[AnswerSection(heading="Intro", content="Body")],
        citations=[Citation(id=1, url="https://example.com", title="Example")],
        stop_rationale=None,
        total_tokens=1234,
        total_duration_seconds=12.5,
    )

    payload = json.loads(event.model_dump_json())

    assert payload["type"] == EventType.STOPPED.value
    assert payload["stop_reason"] == StopReason.JUDGE_CONFIRMED.value
    assert payload["answer_prose"] == "The answer."
    assert payload["answer_sections"] == [{"heading": "Intro", "content": "Body"}]
    assert payload["citations"] == [
        {"id": 1, "url": "https://example.com", "title": "Example"}
    ]
    assert payload["total_tokens"] == 1234
    assert payload["total_duration_seconds"] == 12.5


# ---------------------------------------------------------------------------
# AC-02: Discriminated union — parametrized over every EventType
# ---------------------------------------------------------------------------


def _payload_for(event_type: EventType) -> dict[str, object]:
    """Return a minimal valid payload for the given event type."""
    base: dict[str, object] = {"type": event_type.value}
    extra: dict[str, object]
    match event_type:
        case EventType.QUESTION_ASKED:
            extra = {"question": "What is the capital of France?"}
        case EventType.QUESTION_NORMALIZED:
            extra = {
                "original_question": "quee s una paloma",
                "normalized_question": "¿qué es una paloma?",
                "was_corrected": True,
                "language": "es",
            }
        case EventType.QUESTION_CLASSIFIED:
            extra = {
                "question_type": QuestionType.FACTUAL.value,
                "classifier_confidence": 0.90,
                "complexity_hint": "trivial",
                "heuristic_signals": {"word_count": 5},
            }
        case EventType.PLAN_CREATED:
            extra = {
                "sub_claims": [{"id": "c1", "text": "claim", "status": "pending"}],
                "rationale": "because",
            }
        case EventType.PLAN_CRITIQUED:
            extra = {
                "critique": "ok",
                "issues": [],
                "suggested_changes": [],
                "acceptable": True,
            }
        case EventType.PLAN_REVISED:
            extra = {
                "previous_sub_claims": [],
                "new_sub_claims": [],
                "revision_rationale": "r",
                "attempt_number": 1,
            }
        case EventType.TOOL_CALLED:
            extra = {
                "source_type": SourceType.TAVILY.value,
                "query": "q",
                "query_intent": "i",
            }
        case EventType.EVIDENCE_ADDED:
            extra = {
                "source_type": SourceType.WIKIPEDIA.value,
                "source_url": "https://example.com",
                "source_title": "Example",
                "extracted_text": "text",
                "polarity": EvidencePolarity.SUPPORTS.value,
                "target_claim_id": "c1",
                "confidence": 0.8,
            }
        case EventType.CLAIM_COVERED:
            extra = {
                "claim_id": "c1",
                "claim_text": "t",
                "evidence_ids": [],
                "coverage_rationale": "r",
            }
        case EventType.CLAIM_UNCOVERABLE:
            extra = {
                "claim_id": "c1",
                "claim_text": "t",
                "reason": "r",
                "attempted_sources": [SourceType.TAVILY.value],
            }
        case EventType.SOURCE_FAILED:
            extra = {
                "source_type": SourceType.TAVILY.value,
                "query": "q",
                "error_message": "boom",
                "recoverable": True,
            }
        case EventType.DEEP_FETCH_PERFORMED:
            extra = {
                "source_type": SourceType.TAVILY.value,
                "url": "https://example.com/page",
                "triggered_by_claim_id": "c1",
                "fetch_ms": 123,
                "content_length": 1500,
                "success": True,
            }
        case EventType.QUERY_REFORMULATED:
            extra = {
                "original_query": "original query text",
                "reformulated_query": "reformulated query text",
                "target_claim_id": "c1",
                "reason": "low_relevance",
            }
        case EventType.ECHO_CHAMBER_DETECTED:
            extra = {
                "target_claim_id": "c1",
                "n_sources": 3,
                "date_window_days": 5,
                "diversity_penalty_applied": 0.15,
            }
        case EventType.ROUTE_SELECTED:
            extra = {
                "lane": "standard",
                "reason": "default → STANDARD",
                "question_type": QuestionType.FACTUAL.value,
                "complexity_hint": "standard",
                "temporal_sensitivity": "static",
            }
        case EventType.AMBIGUITY_DETECTED:
            extra = {
                "ambiguous_phrase": "p",
                "possible_interpretations": ["a", "b"],
                "clarification_needed": "?",
            }
        case EventType.CONTRADICTION_DETECTED:
            src = {"url": "https://x", "title": "T", "claim": "c"}
            extra = {
                "claim_id": "c1",
                "source_a": src,
                "source_b": src,
                "nature_of_conflict": "n",
            }
        case EventType.CONTRADICTION_RESOLVED:
            extra = {
                "original_contradiction_id": str(uuid4()),
                "resolution": "r",
                "rationale": "why",
            }
        case EventType.PRIOR_RUN_HINT_REPLAYED:
            extra = {
                "source_run_id": str(uuid4()),
                "source_final_confidence": 0.90,
                "source_stop_reason": StopReason.JUDGE_CONFIRMED.value,
                "normalised_question": "capital of japan",
                "prior_completed_at": "2026-05-27T12:00:00Z",
            }
        case EventType.USER_CONTEXT_CHALLENGED:
            extra = {
                "user_context_claim": "c",
                "contradicting_evidence": "e",
                "source_url": "https://x",
            }
        case EventType.JUDGE_RULED:
            extra = {
                "judge_model": "m",
                "judge_confidence": 0.9,
                "structural_confidence": 0.8,
                "final_confidence": 0.8,
                "threshold": 0.7,
                "passed": True,
                "rationale": "r",
            }
        case EventType.CONFIDENCE_MISMATCH:
            extra = {
                "structural_confidence": 0.9,
                "judge_confidence": 0.4,
                "divergence": 0.5,
                "trust_flag": "warn",
            }
        case EventType.AGENT_ERRORED:
            extra = {
                "error_type": "RuntimeError",
                "error_message": "boom",
                "recoverable": False,
            }
        case EventType.RESUMED_AFTER_ERROR:
            extra = {"original_error_event_id": str(uuid4()), "resume_point": "p"}
        case EventType.RESUMED_AFTER_CANCEL:
            extra = {"cancel_event_id": str(uuid4()), "resume_point": "p"}
        case EventType.STOPPED:
            extra = {"stop_reason": StopReason.JUDGE_CONFIRMED.value}
        case EventType.SATURATION_DETECTED:
            extra = {
                "round_index": 3,
                "novelty": 0.12,
                "k": 3,
                "threshold": 0.15,
            }
        case EventType.JUDGE_PROVIDER_DEGRADED:
            extra = {
                "requested_provider": "anthropic",
                "fallback_provider": "github",
                "error_class": "AuthenticationError",
            }
        case EventType.QUESTION_CLASSIFIED:
            extra = {
                "question_type": "factual",
                "classifier_confidence": 0.92,
            }
        case EventType.PLAN_GAPS_DETECTED:
            extra = {
                "gaps": ["Investigate orbital mechanics"],
                "extra_sub_claim_ids": [str(uuid4())],
            }
        case EventType.NO_PROGRESS_DETECTED:
            extra = {
                "delta_3rounds": 0.03,
                "current_confidence": 0.52,
            }
        case EventType.LANE_ESCALATED:
            extra = {
                "from_lane": "fast",
                "to_lane": "standard",
                "reason": "mini_judge_rejected_or_low_S",
            }
        case EventType.HYPOTHESES_GENERATED:
            extra = {
                "hypotheses": [
                    {
                        "id": str(uuid4()),
                        "text": "Hypothesis A",
                        "priority": 0.8,
                        "verdict": "pending",
                        "evidence_ids": [],
                    }
                ],
            }
        case EventType.AGENT_THOUGHT:
            extra = {"step": 1, "thought": "I should search for X"}
        case EventType.AGENT_ACTION:
            extra = {
                "step": 1,
                "action_type": "search",
                "args": {"query": "q"},
            }
        case EventType.AGENT_OBSERVATION:
            extra = {
                "step": 1,
                "result_summary": "found 3 results",
                "tokens": 42,
            }
        case EventType.HYPOTHESIS_EVALUATED:
            extra = {
                "hypothesis_id": str(uuid4()),
                "verdict": "confirmed",
                "evidence_ids": [str(uuid4())],
            }
        case EventType.HISTORY_SUMMARIZED:
            extra = {"steps_summarized": 8, "summary_tokens": 250}
        case EventType.VERIFICATION_QUESTIONS_GENERATED:
            extra = {
                "questions": [
                    "Did Tokyo become capital in 1868?",
                    "Was Kyoto the previous capital?",
                    "Did the Meiji Restoration occur in 1868?",
                ]
            }
        case EventType.COVE_CONTRADICTION_DETECTED:
            extra = {
                "question": "Did Tokyo become capital in 1868?",
                "contradicting_evidence": "Tokyo became de facto capital in 1868 but was not officially designated until 1943.",
            }
    base.update(extra)
    return base


_EXPECTED_CLASS: dict[EventType, type] = {
    EventType.QUESTION_ASKED: QuestionAskedEvent,
    EventType.QUESTION_NORMALIZED: QuestionNormalizedEvent,
    EventType.QUESTION_CLASSIFIED: QuestionClassifiedEvent,
    EventType.PLAN_CREATED: PlanCreatedEvent,
    EventType.PLAN_CRITIQUED: PlanCritiquedEvent,
    EventType.PLAN_REVISED: PlanRevisedEvent,
    EventType.PLAN_GAPS_DETECTED: PlanGapsDetectedEvent,
    EventType.NO_PROGRESS_DETECTED: NoProgressDetectedEvent,
    EventType.TOOL_CALLED: ToolCalledEvent,
    EventType.EVIDENCE_ADDED: EvidenceAddedEvent,
    EventType.CLAIM_COVERED: ClaimCoveredEvent,
    EventType.CLAIM_UNCOVERABLE: ClaimUncoverableEvent,
    EventType.SOURCE_FAILED: SourceFailedEvent,
    EventType.DEEP_FETCH_PERFORMED: DeepFetchPerformedEvent,
    EventType.QUERY_REFORMULATED: QueryReformulatedEvent,
    EventType.ECHO_CHAMBER_DETECTED: EchoChamberDetectedEvent,
    EventType.ROUTE_SELECTED: RouteSelectedEvent,
    EventType.AMBIGUITY_DETECTED: AmbiguityDetectedEvent,
    EventType.CONTRADICTION_DETECTED: ContradictionDetectedEvent,
    EventType.CONTRADICTION_RESOLVED: ContradictionResolvedEvent,
    EventType.USER_CONTEXT_CHALLENGED: UserContextChallengedEvent,
    EventType.PRIOR_RUN_HINT_REPLAYED: PriorRunHintReplayedEvent,
    EventType.JUDGE_RULED: JudgeRuledEvent,
    EventType.CONFIDENCE_MISMATCH: ConfidenceMismatchEvent,
    EventType.AGENT_ERRORED: AgentErroredEvent,
    EventType.RESUMED_AFTER_ERROR: ResumedAfterErrorEvent,
    EventType.RESUMED_AFTER_CANCEL: ResumedAfterCancelEvent,
    EventType.STOPPED: StoppedEvent,
    EventType.SATURATION_DETECTED: SaturationDetectedEvent,
    EventType.JUDGE_PROVIDER_DEGRADED: JudgeProviderDegradedEvent,
    EventType.LANE_ESCALATED: LaneEscalatedEvent,
    EventType.HYPOTHESES_GENERATED: HypothesesGeneratedEvent,
    EventType.AGENT_THOUGHT: AgentThoughtEvent,
    EventType.AGENT_ACTION: AgentActionEvent,
    EventType.AGENT_OBSERVATION: AgentObservationEvent,
    EventType.HYPOTHESIS_EVALUATED: HypothesisEvaluatedEvent,
    EventType.HISTORY_SUMMARIZED: HistorySummarizedEvent,
    EventType.VERIFICATION_QUESTIONS_GENERATED: VerificationQuestionsGeneratedEvent,
    EventType.COVE_CONTRADICTION_DETECTED: CoveContradictionDetectedEvent,
}


@pytest.mark.parametrize("event_type", list(EventType))
def test_type_adapter_parses_each_event_type(event_type: EventType) -> None:
    """AC-02: discriminator routes each ``type`` value to the right class."""
    payload = _payload_for(event_type)
    parsed = _EVENT_ADAPTER.validate_python(payload)
    assert isinstance(parsed, _EXPECTED_CLASS[event_type])
    assert parsed.type == event_type


# ---------------------------------------------------------------------------
# AC-03: Schema evolution — unknown extra fields are preserved
# ---------------------------------------------------------------------------


def test_extra_fields_preserved_in_model_extra() -> None:
    """AC-03: unknown keys parse and survive in ``model_extra``."""
    payload = {
        "type": EventType.STOPPED.value,
        "stop_reason": StopReason.JUDGE_CONFIRMED.value,
        "future_field": "v2-only",
        "another_future_field": {"nested": 1},
    }
    parsed = _EVENT_ADAPTER.validate_python(payload)
    assert isinstance(parsed, StoppedEvent)
    extra = parsed.model_extra
    assert extra is not None
    assert extra["future_field"] == "v2-only"
    assert extra["another_future_field"] == {"nested": 1}


# ---------------------------------------------------------------------------
# AC-04 & AC-05 + EVENT_TYPE_MAP coverage
# ---------------------------------------------------------------------------


def test_event_type_enum_has_22_values() -> None:
    """AC-04 (IP-25 Phase F): there are exactly 39 event types."""
    assert len(EventType) == 39


def test_forkable_events_exact_membership() -> None:
    """AC-05: ``FORKABLE_EVENTS`` is exactly the documented set."""
    assert {
        EventType.PLAN_CREATED,
        EventType.AMBIGUITY_DETECTED,
        EventType.CONTRADICTION_DETECTED,
        EventType.JUDGE_RULED,
        EventType.STOPPED,
    } == FORKABLE_EVENTS


def test_event_type_map_covers_every_event_type() -> None:
    """Every ``EventType`` value must map to a concrete class."""
    assert set(EVENT_TYPE_MAP.keys()) == {v.value for v in EventType}
    assert len(EVENT_TYPE_MAP) == 39


def test_event_type_map_values_are_unique_classes() -> None:
    classes = list(EVENT_TYPE_MAP.values())
    assert len(set(classes)) == len(classes) == 39


# ---------------------------------------------------------------------------
# Smoke checks for nested DTOs used by events
# ---------------------------------------------------------------------------


def test_sub_claim_defaults_to_pending() -> None:
    claim = SubClaim(id="c1", text="t")
    assert claim.status == "pending"


def test_contradiction_source_extra_allow() -> None:
    src = ContradictionSource.model_validate(
        {"url": "https://x", "title": "T", "claim": "c", "extra_meta": True}
    )
    assert src.model_extra == {"extra_meta": True}


def test_question_asked_round_trip_question_type() -> None:
    """Detected question type survives JSON round-trip."""
    event = QuestionAskedEvent(
        question="What is X?",
        detected_question_type=QuestionType.FACTUAL,
    )
    raw = event.model_dump_json()
    parsed = _EVENT_ADAPTER.validate_json(raw)
    assert isinstance(parsed, QuestionAskedEvent)
    assert parsed.detected_question_type == QuestionType.FACTUAL


def test_evidence_added_event_accepts_authority_tier() -> None:
    """BRD-23 WP-3: ``authority_tier`` is an optional EvidenceAddedEvent field."""
    from app.domain.enums import AuthorityTier

    event = EvidenceAddedEvent(
        source_type=SourceType.TAVILY,
        source_url="https://cdc.gov/x",
        source_title="t",
        extracted_text="x",
        polarity=EvidencePolarity.SUPPORTS,
        target_claim_id="c1",
        confidence=0.9,
        authority_tier=AuthorityTier.PRIMARY_AUTHORITATIVE,
    )
    raw = event.model_dump_json()
    parsed = _EVENT_ADAPTER.validate_json(raw)
    assert isinstance(parsed, EvidenceAddedEvent)
    assert parsed.authority_tier == AuthorityTier.PRIMARY_AUTHORITATIVE


# =============================================================================
# IP-25 Phase 0: New event types
# =============================================================================


def test_query_reformulated_event_serializes() -> None:
    """QueryReformulatedEvent serializes and deserializes correctly."""
    event = QueryReformulatedEvent(
        original_query="what is X?",
        reformulated_query="what is X? context",
        target_claim_id="c1",
        reason="low_relevance",
    )
    raw = event.model_dump_json()
    parsed = _EVENT_ADAPTER.validate_json(raw)
    assert isinstance(parsed, QueryReformulatedEvent)
    assert parsed.original_query == "what is X?"
    assert parsed.reformulated_query == "what is X? context"
    assert parsed.reason == "low_relevance"


def test_echo_chamber_detected_event_serializes() -> None:
    """EchoChamberDetectedEvent serializes and deserializes correctly."""
    event = EchoChamberDetectedEvent(
        target_claim_id="c1",
        n_sources=3,
        date_window_days=5,
        diversity_penalty_applied=0.15,
    )
    raw = event.model_dump_json()
    parsed = _EVENT_ADAPTER.validate_json(raw)
    assert isinstance(parsed, EchoChamberDetectedEvent)
    assert parsed.target_claim_id == "c1"
    assert parsed.n_sources == 3
    assert parsed.date_window_days == 5
    assert parsed.diversity_penalty_applied == 0.15


def test_route_selected_event_serializes() -> None:
    """RouteSelectedEvent serializes and deserializes correctly (IP-25 Phase A)."""
    from app.domain.enums import ComplexityHint, Lane, TemporalSensitivity
    from app.domain.events import RouteSelectedEvent

    event = RouteSelectedEvent(
        lane=Lane.STANDARD,
        reason="complexity=standard → STANDARD",
        question_type=QuestionType.COMPARATIVE,
        complexity_hint=ComplexityHint.STANDARD,
        temporal_sensitivity=TemporalSensitivity.VOLATILE,
    )
    raw = event.model_dump_json()
    parsed = _EVENT_ADAPTER.validate_json(raw)
    assert isinstance(parsed, RouteSelectedEvent)
    assert parsed.lane == Lane.STANDARD
    assert parsed.reason == "complexity=standard → STANDARD"
    assert parsed.question_type == QuestionType.COMPARATIVE


def test_plan_gaps_detected_event_serializes() -> None:
    """PlanGapsDetectedEvent serializes and deserializes correctly (IP-25 Phase B)."""
    from app.domain.events import PlanGapsDetectedEvent

    event = PlanGapsDetectedEvent(
        gaps=["Investigate X aspect", "Check Y perspective"],
        extra_sub_claim_ids=["c3", "c4"],
    )
    raw = event.model_dump_json()
    parsed = _EVENT_ADAPTER.validate_json(raw)
    assert isinstance(parsed, PlanGapsDetectedEvent)
    assert len(parsed.gaps) == 2
    assert "aspect" in parsed.gaps[0]
    assert len(parsed.extra_sub_claim_ids) == 2


def test_no_progress_detected_event_serializes() -> None:
    """NoProgressDetectedEvent serializes and deserializes correctly (IP-25 Phase B)."""
    from app.domain.events import NoProgressDetectedEvent

    event = NoProgressDetectedEvent(
        delta_3rounds=0.03,
        current_confidence=0.68,
    )
    raw = event.model_dump_json()
    parsed = _EVENT_ADAPTER.validate_json(raw)
    assert isinstance(parsed, NoProgressDetectedEvent)
    assert parsed.delta_3rounds == 0.03
    assert parsed.current_confidence == 0.68


def test_lane_escalated_event_serializes() -> None:
    """LaneEscalatedEvent serializes and deserializes correctly (IP-25 Phase C)."""
    from app.domain.enums import Lane
    from app.domain.events import LaneEscalatedEvent

    event = LaneEscalatedEvent(
        from_lane=Lane.FAST,
        to_lane=Lane.STANDARD,
        reason="mini_judge_rejected_or_low_S",
    )
    raw = event.model_dump_json()
    parsed = _EVENT_ADAPTER.validate_json(raw)
    assert isinstance(parsed, LaneEscalatedEvent)
    assert parsed.from_lane == Lane.FAST
    assert parsed.to_lane == Lane.STANDARD
    assert parsed.reason == "mini_judge_rejected_or_low_S"


def test_evidence_added_event_authority_tier_defaults_to_none() -> None:
    """Replay safety: pre-BRD-23 events without ``authority_tier`` parse as ``None``."""
    payload = {
        "type": "EvidenceAdded",
        "source_type": "tavily",
        "source_url": "https://example.com/x",
        "source_title": "t",
        "extracted_text": "x",
        "polarity": "supports",
        "target_claim_id": "c1",
        "confidence": 0.7,
    }
    parsed = _EVENT_ADAPTER.validate_python(payload)
    assert isinstance(parsed, EvidenceAddedEvent)
    assert parsed.authority_tier is None
