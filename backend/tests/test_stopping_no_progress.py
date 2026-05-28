"""Tests for no-progress signal (IP-25 Phase B)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.agent.run_state import RunState
from app.domain.enums import QuestionType
from app.stopping.signals.no_progress import check_no_progress


@pytest.mark.asyncio
async def test_fires_when_3_round_delta_below_threshold():
    """history=[0.5, 0.51, 0.52] → fires (delta=0.02 < 0.05)."""
    state = RunState(
        run_id=uuid4(),
        question="Test question",
        question_type=QuestionType.FACTUAL,
    )
    state.confidence_history = [0.5, 0.51, 0.52]

    fires, delta = await check_no_progress(state)

    assert fires is True
    assert delta == pytest.approx(0.02, abs=0.001)


@pytest.mark.asyncio
async def test_does_not_fire_with_fewer_than_3_rounds():
    """history=[0.5, 0.6] → None (need 3 rounds)."""
    state = RunState(
        run_id=uuid4(),
        question="Test question",
        question_type=QuestionType.FACTUAL,
    )
    state.confidence_history = [0.5, 0.6]

    fires, delta = await check_no_progress(state)

    assert fires is False
    assert delta == 0.0


@pytest.mark.asyncio
async def test_does_not_fire_when_delta_above_threshold():
    """history=[0.5, 0.6, 0.7] → does not fire (delta=0.2 > 0.05)."""
    state = RunState(
        run_id=uuid4(),
        question="Test question",
        question_type=QuestionType.FACTUAL,
    )
    state.confidence_history = [0.5, 0.6, 0.7]

    fires, delta = await check_no_progress(state)

    assert fires is False
    assert delta == pytest.approx(0.2, abs=0.001)


@pytest.mark.asyncio
async def test_emits_no_progress_detected_event():
    """When fires, event includes correct delta + current_confidence."""
    state = RunState(
        run_id=uuid4(),
        question="Test question",
        question_type=QuestionType.FACTUAL,
    )
    state.confidence_history = [0.6, 0.62, 0.63]  # delta=0.03 < 0.05

    fires, delta = await check_no_progress(state)

    assert fires is True
    assert delta == pytest.approx(0.03, abs=0.001)
    # Verify the values that would be included in NoProgressDetectedEvent
    assert state.confidence_history[-1] == 0.63


@pytest.mark.asyncio
async def test_handles_negative_delta():
    """Confidence going DOWN still fires (delta < 0.05)."""
    state = RunState(
        run_id=uuid4(),
        question="Test question",
        question_type=QuestionType.FACTUAL,
    )
    state.confidence_history = [0.7, 0.68, 0.66]  # delta=-0.04 < 0.05

    fires, delta = await check_no_progress(state)

    assert fires is True
    assert delta == pytest.approx(-0.04, abs=0.001)
