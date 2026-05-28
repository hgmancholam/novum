"""Tests for abductive hypothesis generation (IP-25 Phase D)."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.agent.run_state import RunState
from app.agent.tasks.hypotheses import HypothesesList, HypothesisDraft, generate_hypotheses
from app.domain.enums import QuestionType
from app.llm import client as client_module


@pytest.fixture
def mock_create(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock()
    monkeypatch.setattr(client_module.client.chat.completions, "create", mock)
    return mock


@pytest.mark.asyncio
async def test_generate_hypotheses_returns_2_to_4(mock_create: AsyncMock) -> None:
    """Test that hypotheses are clamped to the 2-4 range."""
    # Test upper clamp: LLM returns 5, function returns 4
    mock_create.return_value = HypothesesList(
        items=[
            HypothesisDraft(text=f"Hypothesis {i}", priority=0.9 - i * 0.1)
            for i in range(5)
        ]
    )
    state = RunState(
        run_id=uuid4(),
        question="Why did the Roman Empire fall?",
        question_type=QuestionType.CAUSAL,
    )
    result = await generate_hypotheses(state)
    assert len(result) == 4, "Should clamp 5 hypotheses to 4"
    assert all(h.text.startswith("Hypothesis") for h in result)

    # Test lower bound: LLM returns 1, function raises ValueError
    mock_create.return_value = HypothesesList(
        items=[
            HypothesisDraft(text="Single hypothesis", priority=0.9),
        ]
    )
    state2 = RunState(
        run_id=uuid4(),
        question="Why did X happen?",
        question_type=QuestionType.CAUSAL,
    )
    with pytest.raises(ValueError, match="Expected at least 2 hypotheses"):
        await generate_hypotheses(state2)

    # Test exact range: LLM returns 2, function returns 2
    mock_create.return_value = HypothesesList(
        items=[
            HypothesisDraft(text="Hypothesis A", priority=0.9),
            HypothesisDraft(text="Hypothesis B", priority=0.7),
        ]
    )
    state3 = RunState(
        run_id=uuid4(),
        question="Why did Y happen?",
        question_type=QuestionType.CAUSAL,
    )
    result3 = await generate_hypotheses(state3)
    assert len(result3) == 2, "Should return 2 when LLM returns 2"


@pytest.mark.asyncio
async def test_hypotheses_have_unique_ids(mock_create: AsyncMock) -> None:
    """Test that all generated hypotheses have unique UUIDs."""
    mock_create.return_value = HypothesesList(
        items=[
            HypothesisDraft(text="Military overextension", priority=0.9),
            HypothesisDraft(text="Economic collapse", priority=0.8),
            HypothesisDraft(text="Political instability", priority=0.7),
        ]
    )
    state = RunState(
        run_id=uuid4(),
        question="Why did the Roman Empire fall?",
        question_type=QuestionType.CAUSAL,
    )
    result = await generate_hypotheses(state)

    ids = [h.id for h in result]
    assert len(ids) == len(set(ids)), "All hypothesis IDs must be unique"
    assert all(id is not None for id in ids), "All hypotheses must have IDs"
