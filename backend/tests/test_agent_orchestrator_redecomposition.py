"""Tests for dynamic re-decomposition in orchestrator (IP-25 Phase B)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.agent.orchestrator import AgentOrchestrator
from app.agent.run_state import RunState
from app.agent.states import AgentState
from app.domain.enums import QuestionType
from app.domain.events import PlanGapsDetectedEvent, SubClaim


@pytest.fixture
def base_state():
    """Fixture providing a basic state for re-decomposition tests."""
    state = RunState(
        run_id=uuid4(),
        question="What causes the seasons?",
        question_type=QuestionType.CAUSAL,
        confidence_threshold=0.7,
        max_searches=10,
    )
    state.sub_claims = [
        SubClaim(id="c1", text="Earth's axial tilt", status="covered"),
        SubClaim(id="c2", text="Distance from Sun", status="covered"),
    ]
    state.current_state = AgentState.ANALYZING
    state.search_count = 2
    state.redecomposition_count = 0
    state.max_redecomposition = 1
    return state


@pytest.mark.asyncio
async def test_redecomposition_triggers_once_when_s_low(base_state):
    """S_raw=0.6, threshold=0.7, budget left, count=0 → re-decomp once."""
    events_emitted = []

    async def mock_emit(event):
        events_emitted.append(event)

    # Mock structural confidence to return low score
    with (
        patch("app.agent.orchestrator.analyze_evidence", new_callable=AsyncMock) as mock_analyze,
        patch("app.confidence.calculate_structural_confidence") as mock_calc_conf,
        patch("app.agent.tasks.replan.identify_plan_gaps", new_callable=AsyncMock) as mock_gaps,
    ):
        mock_analyze.return_value = []
        mock_conf = AsyncMock()
        mock_conf.score = 0.6  # Below threshold + 0.10 (0.8)
        mock_calc_conf.return_value = mock_conf
        mock_gaps.return_value = ["Investigate orbital mechanics"]

        orch = AgentOrchestrator(base_state, emit=mock_emit)
        await orch._handle_analyzing()

        # Should emit PlanGapsDetectedEvent
        gaps_events = [e for e in events_emitted if isinstance(e, PlanGapsDetectedEvent)]
        assert len(gaps_events) == 1
        assert len(gaps_events[0].gaps) == 1
        assert "orbital" in gaps_events[0].gaps[0]

        # Should increment redecomposition_count
        assert base_state.redecomposition_count == 1

        # Should transition back to SEARCHING
        assert base_state.current_state == AgentState.SEARCHING

        # Should have added new sub-claim
        assert len(base_state.sub_claims) == 3


@pytest.mark.asyncio
async def test_redecomposition_skipped_when_s_high(base_state):
    """S_raw=0.9 → no re-decomp."""
    events_emitted = []

    async def mock_emit(event):
        events_emitted.append(event)

    with (
        patch("app.agent.orchestrator.analyze_evidence", new_callable=AsyncMock) as mock_analyze,
        patch("app.confidence.calculate_structural_confidence") as mock_calc_conf,
        patch("app.agent.tasks.replan.identify_plan_gaps", new_callable=AsyncMock) as mock_gaps,
    ):
        mock_analyze.return_value = []
        mock_conf = AsyncMock()
        mock_conf.score = 0.9  # Above threshold + 0.10 (0.8)
        mock_calc_conf.return_value = mock_conf

        orch = AgentOrchestrator(base_state, emit=mock_emit)
        base_state.current_state = AgentState.ANALYZING

        await orch._handle_analyzing()

        # Should NOT call identify_plan_gaps
        mock_gaps.assert_not_awaited()

        # Should NOT emit PlanGapsDetectedEvent
        gaps_events = [e for e in events_emitted if isinstance(e, PlanGapsDetectedEvent)]
        assert len(gaps_events) == 0

        # Should NOT increment redecomposition_count
        assert base_state.redecomposition_count == 0

        # Should transition to DRAFTING (all claims covered) or SEARCHING (budget/policy)
        # In this case all claims are covered, so DRAFTING
        assert base_state.current_state in {AgentState.SEARCHING, AgentState.DRAFTING}


@pytest.mark.asyncio
async def test_redecomposition_skipped_when_budget_exhausted(base_state):
    """S_raw=0.6 but budget exhausted → no re-decomp."""
    base_state.search_count = 9  # One away from max_searches=10
    events_emitted = []

    async def mock_emit(event):
        events_emitted.append(event)

    with (
        patch("app.agent.orchestrator.analyze_evidence", new_callable=AsyncMock) as mock_analyze,
        patch("app.confidence.calculate_structural_confidence") as mock_calc_conf,
        patch("app.agent.tasks.replan.identify_plan_gaps", new_callable=AsyncMock) as mock_gaps,
    ):
        mock_analyze.return_value = []
        mock_conf = AsyncMock()
        mock_conf.score = 0.6  # Low score, but no budget
        mock_calc_conf.return_value = mock_conf

        orch = AgentOrchestrator(base_state, emit=mock_emit)
        base_state.current_state = AgentState.ANALYZING

        await orch._handle_analyzing()

        # Should NOT call identify_plan_gaps due to budget constraint
        mock_gaps.assert_not_awaited()

        # Should NOT emit PlanGapsDetectedEvent
        gaps_events = [e for e in events_emitted if isinstance(e, PlanGapsDetectedEvent)]
        assert len(gaps_events) == 0

        assert base_state.redecomposition_count == 0


@pytest.mark.asyncio
async def test_redecomposition_skipped_when_max_reached(base_state):
    """count=1 (max) → no second re-decomp."""
    base_state.redecomposition_count = 1  # Already at max
    events_emitted = []

    async def mock_emit(event):
        events_emitted.append(event)

    with (
        patch("app.agent.orchestrator.analyze_evidence", new_callable=AsyncMock) as mock_analyze,
        patch("app.confidence.calculate_structural_confidence") as mock_calc_conf,
        patch("app.agent.tasks.replan.identify_plan_gaps", new_callable=AsyncMock) as mock_gaps,
    ):
        mock_analyze.return_value = []
        mock_conf = AsyncMock()
        mock_conf.score = 0.6  # Low score, but already re-decomposed
        mock_calc_conf.return_value = mock_conf

        orch = AgentOrchestrator(base_state, emit=mock_emit)
        base_state.current_state = AgentState.ANALYZING

        await orch._handle_analyzing()

        # Should NOT call identify_plan_gaps
        mock_gaps.assert_not_awaited()

        # Should NOT emit PlanGapsDetectedEvent
        gaps_events = [e for e in events_emitted if isinstance(e, PlanGapsDetectedEvent)]
        assert len(gaps_events) == 0

        # Count should stay at 1
        assert base_state.redecomposition_count == 1


@pytest.mark.asyncio
async def test_no_progress_forces_synthesis_and_emits_event():
    """B1: Pre-seed confidence_history with plateau → NoProgressDetectedEvent + transition to DRAFTING."""
    state = RunState(
        run_id=uuid4(),
        question="What causes inflation?",
        question_type=QuestionType.CAUSAL,
        confidence_threshold=0.7,
        max_searches=10,
        max_judge_attempts=5,
    )
    state.sub_claims = [
        SubClaim(id="c1", text="Central bank policy", status="covered"),
        SubClaim(id="c2", text="Supply and demand", status="covered"),
    ]
    state.current_state = AgentState.JUDGING
    state.search_count = 3
    state.judge_attempts = 2
    # Pre-seed confidence history with plateau (delta < 0.05)
    state.confidence_history = [0.5, 0.51, 0.52]
    state.no_progress_triggered = False

    events_emitted = []

    async def mock_emit(event):
        events_emitted.append(event)

    with (
        patch("app.agent.orchestrator.evaluate_with_judge", new_callable=AsyncMock) as mock_judge,
        patch("app.agent.orchestrator.calculate_coverage") as mock_coverage,
        patch("app.agent.orchestrator.calculate_agreement") as mock_agreement,
    ):
        # Judge returns fail (passed=False) so we don't early-stop
        from app.domain.events import JudgeRuledEvent

        mock_judge.return_value = JudgeRuledEvent(
            judge_model="test-model",
            judge_confidence=0.53,
            structural_confidence=0.6,
            threshold=0.7,
            passed=False,
            rationale="Insufficient evidence for key claims",
            final_confidence=0.53,  # Tiny delta from 0.52
        )
        mock_coverage.return_value = 1.0
        mock_agreement.return_value = 0.8

        orch = AgentOrchestrator(state, emit=mock_emit)
        await orch._handle_judging()

        # Should emit NoProgressDetectedEvent
        from app.domain.events import NoProgressDetectedEvent

        no_progress_events = [e for e in events_emitted if isinstance(e, NoProgressDetectedEvent)]
        assert len(no_progress_events) == 1, "NoProgressDetectedEvent should be emitted"
        assert no_progress_events[0].delta_3rounds < 0.05, "Delta should be below threshold"
        assert no_progress_events[0].current_confidence == 0.53

        # Should have set the dedupe flag
        assert state.no_progress_triggered is True

        # Should transition to DRAFTING (force synthesis path)
        assert state.current_state == AgentState.DRAFTING, "Should force DRAFTING transition"
