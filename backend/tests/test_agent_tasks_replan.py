"""Tests for replan task — dynamic gap detection (IP-25 Phase B)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.agent.run_state import RunState
from app.agent.tasks.replan import identify_plan_gaps
from app.domain.enums import QuestionType
from app.domain.events import SubClaim


@pytest.mark.asyncio
async def test_identify_plan_gaps_returns_list():
    """Planner LLM returns 2 gaps → function returns list of 2."""
    state = RunState(
        run_id=uuid4(),
        question="What causes earthquakes?",
        question_type=QuestionType.CAUSAL,
    )
    state.sub_claims = [
        SubClaim(id="c1", text="Tectonic plate movement", status="covered"),
        SubClaim(id="c2", text="Volcanic activity", status="pending"),
    ]

    with patch("app.agent.tasks.replan.llm") as mock_llm:
        mock_result = AsyncMock()
        mock_result.gaps = ["Investigate seismic wave patterns", "Check historical frequency data"]
        mock_llm.call = AsyncMock(return_value=mock_result)

        gaps = await identify_plan_gaps(state)

        assert isinstance(gaps, list)
        assert len(gaps) == 2
        assert "seismic wave" in gaps[0]
        assert "historical frequency" in gaps[1]
        mock_llm.call.assert_awaited_once()


@pytest.mark.asyncio
async def test_identify_plan_gaps_caps_at_three():
    """LLM returns 5 gaps → function caps result at 3."""
    state = RunState(
        run_id=uuid4(),
        question="What causes climate change?",
        question_type=QuestionType.CAUSAL,
    )
    state.sub_claims = [
        SubClaim(id="c1", text="CO2 emissions", status="covered"),
    ]

    with patch("app.agent.tasks.replan.llm") as mock_llm:
        mock_result = AsyncMock()
        mock_result.gaps = [
            "Gap 1",
            "Gap 2",
            "Gap 3",
            "Gap 4",
            "Gap 5",
        ]
        mock_llm.call = AsyncMock(return_value=mock_result)

        gaps = await identify_plan_gaps(state)

        assert len(gaps) == 3
        assert gaps == ["Gap 1", "Gap 2", "Gap 3"]


@pytest.mark.asyncio
async def test_identify_plan_gaps_handles_empty_response():
    """LLM returns empty list → function returns empty list."""
    state = RunState(
        run_id=uuid4(),
        question="What is the capital of France?",
        question_type=QuestionType.FACTUAL,
    )
    state.sub_claims = [
        SubClaim(id="c1", text="Paris is the capital", status="covered"),
    ]

    with patch("app.agent.tasks.replan.llm") as mock_llm:
        mock_result = AsyncMock()
        mock_result.gaps = []
        mock_llm.call = AsyncMock(return_value=mock_result)

        gaps = await identify_plan_gaps(state)

        assert gaps == []


@pytest.mark.asyncio
async def test_identify_plan_gaps_handles_llm_failure():
    """LLM call raises exception → function returns empty list gracefully."""
    state = RunState(
        run_id=uuid4(),
        question="Test question",
        question_type=QuestionType.FACTUAL,
    )

    with patch("app.agent.tasks.replan.llm") as mock_llm:
        mock_llm.call = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

        gaps = await identify_plan_gaps(state)

        assert gaps == []  # Graceful degradation
