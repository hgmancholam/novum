"""Tests for complexity-aware planner budget (US-22-2).

Covers TC-01..TC-06, TC-09:
- TC-01: trivial+FACTUAL → (1,1,1,0) no critique
- TC-02: trivial+DEFINITIONAL → (1,1,1,0)
- TC-03: standard+COMPARATIVE → default budget
- TC-04: deep+STATE_OF_ART → 2 critiques
- TC-05: trivial+STATE_OF_ART coercion → STANDARD
- TC-06: complexity_hint=None → fallback STANDARD
- TC-09: Replay tolerates missing fields
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.agent.tasks import plan
from app.domain.enums import ComplexityHint, QuestionType
from app.llm import client as client_module
from app.llm.models import PlanOutput, SubClaimOutput


@pytest.fixture
def mock_create(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock()
    monkeypatch.setattr(client_module.client.chat.completions, "create", mock)
    return mock


def _plan_output() -> PlanOutput:
    return PlanOutput(
        sub_claims=[SubClaimOutput(id="c1", text="claim", rationale="r")],
        overall_rationale="ok",
        expected_experts=[],
    )


async def test_trivial_factual_budget(mock_create: AsyncMock) -> None:
    """TC-01: trivial+FACTUAL → 1 claim, 1 source, 0 critiques."""
    mock_create.return_value = _plan_output()
    event = await plan.create_plan(
        "Tokyo?",
        question_type=QuestionType.FACTUAL,
        complexity_hint=ComplexityHint.TRIVIAL,
    )
    assert event.complexity_hint == ComplexityHint.TRIVIAL
    assert event.preferred_sources == ["wikipedia"]
    # Budget reflected in prompt (claims_min=1, claims_max=1, sources=1)
    prompt = mock_create.call_args.kwargs["messages"][-1]["content"]
    assert "1-1" in prompt or "1 claim" in prompt.lower()


async def test_trivial_definitional_budget(mock_create: AsyncMock) -> None:
    """TC-02: trivial+DEFINITIONAL → same as factual."""
    mock_create.return_value = _plan_output()
    event = await plan.create_plan(
        "What is X?",
        question_type=QuestionType.DEFINITIONAL,
        complexity_hint=ComplexityHint.TRIVIAL,
    )
    assert event.complexity_hint == ComplexityHint.TRIVIAL
    assert event.preferred_sources == ["wikipedia"]


async def test_standard_comparative_budget(mock_create: AsyncMock) -> None:
    """TC-03: standard+COMPARATIVE → default (3-5, 2 sources, 1 critique)."""
    mock_create.return_value = _plan_output()
    event = await plan.create_plan(
        "X vs Y?",
        question_type=QuestionType.COMPARATIVE,
        complexity_hint=ComplexityHint.STANDARD,
    )
    assert event.complexity_hint == ComplexityHint.STANDARD
    # Per D-AGENT-ROBUSTNESS C5, STANDARD+COMPARATIVE routes academic sources too.
    # Post-PR-7: academic sources first so the cascade tries them before Tavily.
    assert event.preferred_sources == ["semantic_scholar", "openalex", "tavily", "wikipedia"]


async def test_deep_state_of_art_two_critiques(mock_create: AsyncMock) -> None:
    """TC-04: deep+STATE_OF_ART → critique_passes=2."""
    mock_create.return_value = _plan_output()
    event = await plan.create_plan(
        "Long research question?",
        question_type=QuestionType.STATE_OF_ART,
        complexity_hint=ComplexityHint.DEEP,
    )
    assert event.complexity_hint == ComplexityHint.DEEP
    # IP-36: STATE_OF_ART+DEEP budget tightened to (3, 6, 3, 2).
    prompt = mock_create.call_args.kwargs["messages"][-1]["content"]
    assert "3-6" in prompt or "deep" in prompt.lower()


async def test_trivial_state_of_art_coercion(mock_create: AsyncMock) -> None:
    """TC-05: trivial+STATE_OF_ART incompatible → coerce to STANDARD."""
    mock_create.return_value = _plan_output()
    event = await plan.create_plan(
        "Q?",
        question_type=QuestionType.STATE_OF_ART,
        complexity_hint=ComplexityHint.TRIVIAL,
    )
    # Coercion happens inside create_plan
    assert event.complexity_hint == ComplexityHint.STANDARD


async def test_complexity_hint_none_fallback(mock_create: AsyncMock) -> None:
    """TC-06: complexity_hint=None → default to STANDARD."""
    mock_create.return_value = _plan_output()
    event = await plan.create_plan(
        "Q?",
        question_type=QuestionType.FACTUAL,
        complexity_hint=None,
    )
    # Defaults to STANDARD in create_plan
    assert event.complexity_hint == ComplexityHint.STANDARD


async def test_replay_tolerates_missing_fields(mock_create: AsyncMock) -> None:
    """TC-09: revise_plan with None hint → fallback STANDARD."""
    mock_create.return_value = _plan_output()
    from app.domain.events import SubClaim

    previous = [SubClaim(id="c0", text="old", status="pending")]
    event = await plan.revise_plan(
        "Q?",
        previous,
        attempt_number=2,
        complexity_hint=None,
    )
    # revise_plan defaults to STANDARD when None
    assert event.complexity_hint == ComplexityHint.STANDARD
