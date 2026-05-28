"""Intra-loop stopping signal tests (IP-25 Phase E)."""

from uuid import uuid4

import pytest

from app.agent.run_state import RunState
from app.domain.enums import StopReason
from app.domain.hypothesis import Hypothesis
from app.seams.stopping import SignalResult, StopContext
from app.stopping.react_intra_loop import (
    AllHypothesesRefutedSignal,
    HypothesisConfirmedSignal,
    ReactContradictionSignal,
    ReactStepCapSignal,
    evaluate_react_intra_loop,
)


@pytest.mark.asyncio
async def test_hypothesis_confirmed_signal_fires() -> None:
    """Test HypothesisConfirmedSignal returns STOP when hypothesis confirmed with S≥0.75."""
    # Setup state with one confirmed hypothesis and high confidence
    state = RunState(
        run_id=uuid4(),
        question="Test question?",
        owner_username="test_user",
        hypotheses=[
            Hypothesis(text="Hypothesis 1", priority=0.9, verdict="confirmed"),
            Hypothesis(text="Hypothesis 2", priority=0.7, verdict="pending"),
        ],
        last_structural_confidence=0.8,
    )

    # Build StopContext
    context = StopContext(
        search_count=5,
        max_searches=10,
        structural_confidence=0.8,
        judge_confidence=None,
        coverage=0.8,
        agreement=0.0,
        diversity=0.0,
        no_conflict=1.0,
        threshold=0.7,
        has_ambiguity=False,
        has_contradictions=False,
        uncoverable_claims=0,
        covered_claims=5,
        total_claims=10,
        judge_passed=None,
    )

    # Evaluate signal
    signal = HypothesisConfirmedSignal(state)
    result = await signal.evaluate(context)

    # Assertions
    assert result.result == SignalResult.STOP
    assert result.stop_reason == StopReason.JUDGE_CONFIRMED
    assert "confirmed" in result.explanation.lower()
    assert result.confidence == 0.8


@pytest.mark.asyncio
async def test_all_hypotheses_refuted_signal() -> None:
    """Test AllHypothesesRefutedSignal returns STOP when all hypotheses refuted."""
    # Setup state with all hypotheses refuted
    state = RunState(
        run_id=uuid4(),
        question="Test question?",
        owner_username="test_user",
        hypotheses=[
            Hypothesis(text="Hypothesis 1", priority=0.9, verdict="refuted"),
            Hypothesis(text="Hypothesis 2", priority=0.7, verdict="refuted"),
            Hypothesis(text="Hypothesis 3", priority=0.6, verdict="refuted"),
        ],
        last_structural_confidence=0.5,
    )

    # Build StopContext
    context = StopContext(
        search_count=5,
        max_searches=10,
        structural_confidence=0.5,
        judge_confidence=None,
        coverage=0.6,
        agreement=0.0,
        diversity=0.0,
        no_conflict=1.0,
        threshold=0.7,
        has_ambiguity=False,
        has_contradictions=False,
        uncoverable_claims=0,
        covered_claims=5,
        total_claims=10,
        judge_passed=None,
    )

    # Evaluate signal
    signal = AllHypothesesRefutedSignal(state)
    result = await signal.evaluate(context)

    # Assertions
    assert result.result == SignalResult.STOP
    assert result.stop_reason == StopReason.STOPPED_BY_BUDGET
    assert "all" in result.explanation.lower()
    assert "refuted" in result.explanation.lower()


@pytest.mark.asyncio
async def test_react_step_cap_signal() -> None:
    """Test ReactStepCapSignal returns STOP when react_step_count >= max_react_steps."""
    # Setup state with step count at cap
    state = RunState(
        run_id=uuid4(),
        question="Test question?",
        owner_username="test_user",
        hypotheses=[
            Hypothesis(text="Hypothesis 1", priority=0.9, verdict="pending"),
        ],
        max_react_steps=5,
        react_step_count=5,
        last_structural_confidence=0.5,
    )

    # Build StopContext
    context = StopContext(
        search_count=5,
        max_searches=10,
        structural_confidence=0.5,
        judge_confidence=None,
        coverage=0.6,
        agreement=0.0,
        diversity=0.0,
        no_conflict=1.0,
        threshold=0.7,
        has_ambiguity=False,
        has_contradictions=False,
        uncoverable_claims=0,
        covered_claims=5,
        total_claims=10,
        judge_passed=None,
    )

    # Evaluate signal
    signal = ReactStepCapSignal(state)
    result = await signal.evaluate(context)

    # Assertions
    assert result.result == SignalResult.STOP
    assert result.stop_reason == StopReason.STOPPED_BY_BUDGET
    assert "budget exhausted" in result.explanation.lower()


@pytest.mark.asyncio
async def test_react_contradiction_signal() -> None:
    """Test ReactContradictionSignal fires when 2+ confirmed hypotheses have disjoint evidence."""
    # Setup state with two confirmed hypotheses with disjoint evidence
    hyp1 = Hypothesis(
        text="Hypothesis 1",
        priority=0.9,
        verdict="confirmed",
        evidence_ids=[uuid4(), uuid4()],
    )
    hyp2 = Hypothesis(
        text="Hypothesis 2",
        priority=0.8,
        verdict="confirmed",
        evidence_ids=[uuid4(), uuid4()],  # Different evidence IDs → disjoint
    )

    state = RunState(
        run_id=uuid4(),
        question="Test question?",
        owner_username="test_user",
        hypotheses=[hyp1, hyp2],
        last_structural_confidence=0.7,
    )

    # Build StopContext
    context = StopContext(
        search_count=5,
        max_searches=10,
        structural_confidence=0.7,
        judge_confidence=None,
        coverage=0.7,
        agreement=0.0,
        diversity=0.0,
        no_conflict=1.0,
        threshold=0.7,
        has_ambiguity=False,
        has_contradictions=False,
        uncoverable_claims=0,
        covered_claims=5,
        total_claims=10,
        judge_passed=None,
    )

    # Evaluate signal
    signal = ReactContradictionSignal(state)
    result = await signal.evaluate(context)

    # Assertions
    assert result.result == SignalResult.STOP
    assert result.stop_reason == StopReason.STOPPED_BY_BUDGET
    assert "contradictory" in result.explanation.lower()


@pytest.mark.asyncio
async def test_evaluate_react_intra_loop_returns_first_stop() -> None:
    """Test evaluate_react_intra_loop returns first firing signal in priority order."""
    # Setup state with multiple stop conditions
    # Both HypothesisConfirmedSignal (priority 5) and ReactStepCapSignal (priority 20) would fire
    # Should return HypothesisConfirmedSignal due to higher priority
    state = RunState(
        run_id=uuid4(),
        question="Test question?",
        owner_username="test_user",
        hypotheses=[
            Hypothesis(text="Hypothesis 1", priority=0.9, verdict="confirmed"),
        ],
        last_structural_confidence=0.8,
        max_react_steps=3,
        react_step_count=3,
    )

    # Execute aggregate evaluator
    result = await evaluate_react_intra_loop(state)

    # Assertions
    assert result is not None
    assert result.result == SignalResult.STOP
    # Should be HypothesisConfirmedSignal (higher priority)
    assert result.signal_name == "HypothesisConfirmed"
    assert result.stop_reason == StopReason.JUDGE_CONFIRMED


@pytest.mark.asyncio
async def test_evaluate_react_intra_loop_returns_none_when_no_stop() -> None:
    """Test evaluate_react_intra_loop returns None when no stopping condition met."""
    # Setup state with no terminal conditions
    state = RunState(
        run_id=uuid4(),
        question="Test question?",
        owner_username="test_user",
        hypotheses=[
            Hypothesis(text="Hypothesis 1", priority=0.9, verdict="pending"),
            Hypothesis(text="Hypothesis 2", priority=0.7, verdict="pending"),
        ],
        last_structural_confidence=0.5,
        max_react_steps=10,
        react_step_count=2,
    )

    # Execute aggregate evaluator
    result = await evaluate_react_intra_loop(state)

    # Assertions
    assert result is None


@pytest.mark.asyncio
async def test_hypothesis_confirmed_defers_when_confidence_low() -> None:
    """Test HypothesisConfirmedSignal defers when S < 0.75."""
    # Setup state with confirmed hypothesis but low confidence
    state = RunState(
        run_id=uuid4(),
        question="Test question?",
        owner_username="test_user",
        hypotheses=[
            Hypothesis(text="Hypothesis 1", priority=0.9, verdict="confirmed"),
        ],
        last_structural_confidence=0.6,  # Below 0.75 threshold
    )

    context = StopContext(
        search_count=5,
        max_searches=10,
        structural_confidence=0.6,
        judge_confidence=None,
        coverage=0.6,
        agreement=0.0,
        diversity=0.0,
        no_conflict=1.0,
        threshold=0.7,
        has_ambiguity=False,
        has_contradictions=False,
        uncoverable_claims=0,
        covered_claims=5,
        total_claims=10,
        judge_passed=None,
    )

    # Evaluate signal
    signal = HypothesisConfirmedSignal(state)
    result = await signal.evaluate(context)

    # Assertions
    assert result.result == SignalResult.DEFER
    assert "confirmed: 1" in result.explanation.lower()


@pytest.mark.asyncio
async def test_all_refuted_defers_when_some_pending() -> None:
    """Test AllHypothesesRefutedSignal defers when some hypotheses still pending."""
    # Setup state with mixed verdicts
    state = RunState(
        run_id=uuid4(),
        question="Test question?",
        owner_username="test_user",
        hypotheses=[
            Hypothesis(text="Hypothesis 1", priority=0.9, verdict="refuted"),
            Hypothesis(text="Hypothesis 2", priority=0.7, verdict="pending"),
        ],
        last_structural_confidence=0.5,
    )

    context = StopContext(
        search_count=5,
        max_searches=10,
        structural_confidence=0.5,
        judge_confidence=None,
        coverage=0.6,
        agreement=0.0,
        diversity=0.0,
        no_conflict=1.0,
        threshold=0.7,
        has_ambiguity=False,
        has_contradictions=False,
        uncoverable_claims=0,
        covered_claims=5,
        total_claims=10,
        judge_passed=None,
    )

    # Evaluate signal
    signal = AllHypothesesRefutedSignal(state)
    result = await signal.evaluate(context)

    # Assertions
    assert result.result == SignalResult.DEFER
    assert "refuted: 1/2" in result.explanation.lower()


@pytest.mark.asyncio
async def test_contradiction_defers_with_overlapping_evidence() -> None:
    """Test ReactContradictionSignal defers when confirmed hypotheses share evidence."""
    # Setup state with two confirmed hypotheses sharing some evidence
    shared_evidence_id = uuid4()
    hyp1 = Hypothesis(
        text="Hypothesis 1",
        priority=0.9,
        verdict="confirmed",
        evidence_ids=[shared_evidence_id, uuid4()],
    )
    hyp2 = Hypothesis(
        text="Hypothesis 2",
        priority=0.8,
        verdict="confirmed",
        evidence_ids=[shared_evidence_id, uuid4()],  # Shares one evidence ID
    )

    state = RunState(
        run_id=uuid4(),
        question="Test question?",
        owner_username="test_user",
        hypotheses=[hyp1, hyp2],
        last_structural_confidence=0.7,
    )

    context = StopContext(
        search_count=5,
        max_searches=10,
        structural_confidence=0.7,
        judge_confidence=None,
        coverage=0.7,
        agreement=0.0,
        diversity=0.0,
        no_conflict=1.0,
        threshold=0.7,
        has_ambiguity=False,
        has_contradictions=False,
        uncoverable_claims=0,
        covered_claims=5,
        total_claims=10,
        judge_passed=None,
    )

    # Evaluate signal
    signal = ReactContradictionSignal(state)
    result = await signal.evaluate(context)

    # Assertions
    assert result.result == SignalResult.DEFER
    assert "overlapping evidence" in result.explanation.lower()
