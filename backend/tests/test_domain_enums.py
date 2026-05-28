"""Tests for domain enums (BRD-02 §4.2, WP-3 amendment).

Cross-checks enum values and counts against the Alembic migrations.

Amendment 2026-05-27 WP-3: ``StopReason`` collapsed from 7 to 4 values
(migration 002). ``QuestionType`` extended to 8 values (Types 6/7/8 no
longer short-circuit); ``AnswerKind`` introduced (RF-17).
"""

from app.domain.enums import (
    AnswerKind,
    AuthorityTier,
    ComplexityHint,
    EventType,
    EvidencePolarity,
    OutputFormat,
    QuestionType,
    SourceType,
    StopReason,
)


def test_stop_reason_has_exactly_4_values() -> None:
    """WP-3: StopReason collapsed to 4 values."""
    assert len(StopReason) == 4


def test_stop_reason_values() -> None:
    """WP-3: Only judge_confirmed, stopped_by_budget, user_cancelled, errored."""
    expected = {
        "judge_confirmed",
        "stopped_by_budget",
        "user_cancelled",
        "errored",
    }
    assert {v.value for v in StopReason} == expected


def test_question_type_has_exactly_8_values() -> None:
    assert len(QuestionType) == 8


def test_question_type_values() -> None:
    expected = {
        "factual",
        "comparative",
        "definitional",
        "state_of_art",
        "causal",
        "predictive_future",
        "subjective_opinion",
        "personal_private",
    }
    assert {v.value for v in QuestionType} == expected


def test_answer_kind_has_exactly_6_values() -> None:
    assert len(AnswerKind) == 6


def test_answer_kind_values() -> None:
    expected = {
        "direct",
        "weighted",
        "scenario",
        "tradeoff",
        "ethical_redirect",
        "best_effort",
    }
    assert {v.value for v in AnswerKind} == expected


def test_output_format_has_exactly_2_values() -> None:
    assert len(OutputFormat) == 2


def test_output_format_values() -> None:
    assert {v.value for v in OutputFormat} == {"prose", "structured"}


def test_event_type_has_exactly_24_values() -> None:
    """BRD-22 + BRD-23 WP-2: 25 event types after DeepFetchPerformed."""
    assert len(EventType) == 25


def test_event_type_values() -> None:
    expected = {
        "QuestionAsked",
        "QuestionNormalized",
        "QuestionClassified",
        "PlanCreated",
        "PlanCritiqued",
        "PlanRevised",
        "ToolCalled",
        "EvidenceAdded",
        "ClaimCovered",
        "ClaimUncoverable",
        "SourceFailed",
        "AmbiguityDetected",
        "ContradictionDetected",
        "ContradictionResolved",
        "UserContextChallenged",
        "PriorRunHintReplayed",
        "JudgeRuled",
        "ConfidenceMismatch",
        "AgentErrored",
        "ResumedAfterError",
        "ResumedAfterCancel",
        "Stopped",
        "SaturationDetected",
        "JudgeProviderDegraded",
            "DeepFetchPerformed",
    }
    assert {v.value for v in EventType} == expected


def test_evidence_polarity_values() -> None:
    assert {v.value for v in EvidencePolarity} == {"supports", "contradicts", "neutral"}


def test_source_type_values() -> None:
    assert {v.value for v in SourceType} == {"tavily", "wikipedia", "semantic_scholar", "openalex"}


def test_enums_are_string_subclass() -> None:
    """StrEnum members must be usable directly as ``str``."""
    assert StopReason.JUDGE_CONFIRMED == "judge_confirmed"
    assert EventType.STOPPED == "Stopped"
    assert QuestionType.FACTUAL == "factual"


def test_complexity_hint_has_exactly_3_values() -> None:
    """BRD-22: ComplexityHint enum."""
    assert len(ComplexityHint) == 3


def test_complexity_hint_values() -> None:
    """BRD-22: trivial, standard, deep."""
    expected = {"trivial", "standard", "deep"}
    assert {v.value for v in ComplexityHint} == expected


def test_authority_tier_values() -> None:
    """BRD-23 §4.7: 4 tiers."""
    expected = {
        "primary_authoritative",
        "reputable_secondary",
        "general",
        "low_signal",
    }
    assert {v.value for v in AuthorityTier} == expected
    assert AuthorityTier.PRIMARY_AUTHORITATIVE == "primary_authoritative"
