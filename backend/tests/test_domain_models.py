"""Tests for run DTOs and confidence models (BRD-02 §4.4 / §4.5)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.confidence import ConfidenceResult, StructuralConfidence
from app.domain.enums import OutputFormat, QuestionType, StopReason
from app.domain.run import RunCreate, RunForkRequest, RunListItem, RunResponse

# ---------------------------------------------------------------------------
# RunCreate validation
# ---------------------------------------------------------------------------


def test_run_create_defaults() -> None:
    run = RunCreate(question="What is the capital of France?")
    assert run.user_context is None
    assert run.output_format == OutputFormat.PROSE
    assert run.confidence_threshold == 0.7


def test_run_create_question_min_length() -> None:
    with pytest.raises(ValidationError):
        RunCreate(question="too short")


def test_run_create_question_max_length() -> None:
    with pytest.raises(ValidationError):
        RunCreate(question="x" * 2001)


def test_run_create_confidence_threshold_lower_bound() -> None:
    with pytest.raises(ValidationError):
        RunCreate(
            question="What is the capital of France?",
            confidence_threshold=-0.01,
        )


def test_run_create_confidence_threshold_upper_bound() -> None:
    with pytest.raises(ValidationError):
        RunCreate(
            question="What is the capital of France?",
            confidence_threshold=1.01,
        )


def test_run_create_confidence_threshold_inclusive_bounds() -> None:
    low = RunCreate(question="What is the capital of France?", confidence_threshold=0.0)
    high = RunCreate(question="What is the capital of France?", confidence_threshold=1.0)
    assert low.confidence_threshold == 0.0
    assert high.confidence_threshold == 1.0


def test_run_create_user_context_max_length() -> None:
    with pytest.raises(ValidationError):
        RunCreate(
            question="What is the capital of France?",
            user_context="x" * 1001,
        )


# ---------------------------------------------------------------------------
# RunResponse / RunListItem / RunForkRequest shape
# ---------------------------------------------------------------------------


def test_run_response_accepts_optional_fields() -> None:
    response = RunResponse(
        id=uuid4(),
        owner_username="alice",
        question="What is the capital of France?",
        user_context=None,
        question_type=QuestionType.FACTUAL,
        output_format=OutputFormat.STRUCTURED,
        confidence_threshold=0.8,
        started_at=datetime.now(UTC),
        stopped_at=None,
        stop_reason=None,
        parent_run_id=None,
        forked_at_event_id=None,
    )
    assert response.question_type == QuestionType.FACTUAL
    assert response.stop_reason is None


def test_run_list_item_minimal() -> None:
    item = RunListItem(
        id=uuid4(),
        username="alice",
        question="Q",
        started_at=datetime.now(UTC),
        stopped_at=None,
        stop_reason=StopReason.JUDGE_CONFIRMED,
    )
    assert item.stop_reason == StopReason.JUDGE_CONFIRMED


def test_run_fork_request() -> None:
    event_id = uuid4()
    request = RunForkRequest(event_id=event_id)
    assert request.event_id == event_id


# ---------------------------------------------------------------------------
# StructuralConfidence.score weighted formula
# ---------------------------------------------------------------------------


def test_structural_confidence_score_all_ones() -> None:
    s = StructuralConfidence(coverage=1.0, agreement=1.0, diversity=1.0, no_conflict=1.0)
    assert s.score == pytest.approx(1.0)


def test_structural_confidence_score_all_zero() -> None:
    s = StructuralConfidence(coverage=0.0, agreement=0.0, diversity=0.0, no_conflict=0.0)
    assert s.score == pytest.approx(0.0)


def test_structural_confidence_score_weighted_formula() -> None:
    """S = 0.35*c + 0.30*a + 0.20*d + 0.15*n."""
    s = StructuralConfidence(coverage=0.8, agreement=0.6, diversity=0.4, no_conflict=0.2)
    expected = 0.35 * 0.8 + 0.30 * 0.6 + 0.20 * 0.4 + 0.15 * 0.2
    assert s.score == pytest.approx(expected)


def test_structural_confidence_rejects_out_of_range() -> None:
    with pytest.raises(ValidationError):
        StructuralConfidence(coverage=1.5, agreement=0.5, diversity=0.5, no_conflict=0.5)
    with pytest.raises(ValidationError):
        StructuralConfidence(coverage=0.5, agreement=-0.1, diversity=0.5, no_conflict=0.5)


# ---------------------------------------------------------------------------
# ConfidenceResult shape
# ---------------------------------------------------------------------------


def test_confidence_result_shape() -> None:
    structural = StructuralConfidence(
        coverage=0.9, agreement=0.8, diversity=0.7, no_conflict=0.6
    )
    result = ConfidenceResult(
        structural=structural,
        judge=0.85,
        final=min(structural.score, 0.85),
        threshold=0.7,
        passed=True,
    )
    assert result.judge == 0.85
    assert result.passed is True
    assert result.final == pytest.approx(min(structural.score, 0.85))


def test_confidence_result_rejects_out_of_range() -> None:
    structural = StructuralConfidence(
        coverage=0.5, agreement=0.5, diversity=0.5, no_conflict=0.5
    )
    with pytest.raises(ValidationError):
        ConfidenceResult(
            structural=structural,
            judge=1.5,
            final=0.5,
            threshold=0.7,
            passed=False,
        )
