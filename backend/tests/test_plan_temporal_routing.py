"""BRD-23 WP-1: planner temporal-routing tests for ``preferred_sources``."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.agent.tasks import plan
from app.domain.enums import ComplexityHint, QuestionType, TemporalSensitivity
from app.llm import client as client_module
from app.llm.models import PlanOutput, SubClaimOutput


@pytest.fixture
def mock_create(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock()
    monkeypatch.setattr(client_module.client.chat.completions, "create", mock)
    return mock


def _plan_output() -> PlanOutput:
    return PlanOutput(
        sub_claims=[SubClaimOutput(id="c1", text="x", rationale="r")],
        overall_rationale="ok",
    )


async def test_realtime_routes_tavily_only(mock_create: AsyncMock) -> None:
    mock_create.return_value = _plan_output()
    event = await plan.create_plan(
        "live score?",
        question_type=QuestionType.FACTUAL,
        complexity_hint=ComplexityHint.TRIVIAL,
        temporal_sensitivity=TemporalSensitivity.REALTIME,
    )
    assert event.preferred_sources == ["tavily"]
    assert event.temporal_sensitivity == TemporalSensitivity.REALTIME


async def test_volatile_routes_tavily_first_then_wiki(mock_create: AsyncMock) -> None:
    mock_create.return_value = _plan_output()
    event = await plan.create_plan(
        "latest llm?",
        question_type=QuestionType.STATE_OF_ART,
        complexity_hint=ComplexityHint.STANDARD,
        temporal_sensitivity=TemporalSensitivity.VOLATILE,
    )
    assert event.preferred_sources == ["tavily", "wikipedia"]


async def test_static_trivial_factual_keeps_wikipedia_only(mock_create: AsyncMock) -> None:
    mock_create.return_value = _plan_output()
    event = await plan.create_plan(
        "Capital of Japan?",
        question_type=QuestionType.FACTUAL,
        complexity_hint=ComplexityHint.TRIVIAL,
        temporal_sensitivity=TemporalSensitivity.STATIC,
    )
    assert event.preferred_sources == ["wikipedia"]


async def test_slow_changing_no_override(mock_create: AsyncMock) -> None:
    """Non-trivial slow_changing topics leave preferred_sources unset (use defaults)."""
    mock_create.return_value = _plan_output()
    event = await plan.create_plan(
        "Population of Brazil?",
        question_type=QuestionType.FACTUAL,
        complexity_hint=ComplexityHint.STANDARD,
        temporal_sensitivity=TemporalSensitivity.SLOW_CHANGING,
    )
    assert event.preferred_sources is None
    assert event.temporal_sensitivity == TemporalSensitivity.SLOW_CHANGING
