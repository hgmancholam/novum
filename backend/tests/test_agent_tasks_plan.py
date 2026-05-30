"""Tests for ``app.agent.tasks.plan``."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.agent.tasks import plan
from app.domain.events import SubClaim
from app.llm import client as client_module
from app.llm.models import CritiqueOutput, PlanOutput, SubClaimOutput


@pytest.fixture
def mock_create(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock()
    monkeypatch.setattr(client_module.client.chat.completions, "create", mock)
    return mock


async def test_create_plan_returns_event_with_pending_sub_claims(
    mock_create: AsyncMock,
) -> None:
    mock_create.return_value = PlanOutput(
        sub_claims=[
            SubClaimOutput(id="c1", text="claim 1", rationale="r1"),
            SubClaimOutput(id="c2", text="claim 2", rationale="r2"),
        ],
        overall_rationale="ok",
    )
    event = await plan.create_plan("What is X?")
    assert event.rationale == "ok"
    assert [c.id for c in event.sub_claims] == ["c1", "c2"]
    assert all(c.status == "pending" for c in event.sub_claims)


async def test_critique_plan_acceptable(mock_create: AsyncMock) -> None:
    mock_create.return_value = CritiqueOutput(
        acceptable=True, summary="looks good", issues=[], suggested_changes=[]
    )
    event = await plan.critique_plan(
        "Q?",
        [SubClaim(id="c1", text="x", status="pending")],
    )
    assert event.acceptable is True
    assert event.issues == []


async def test_critique_plan_not_acceptable(mock_create: AsyncMock) -> None:
    mock_create.return_value = CritiqueOutput(
        acceptable=False,
        summary="bad",
        issues=["missing scope"],
        suggested_changes=["narrow scope"],
    )
    event = await plan.critique_plan(
        "Q?",
        [SubClaim(id="c1", text="x", status="pending")],
    )
    assert event.acceptable is False
    assert event.issues == ["missing scope"]
    assert event.suggested_changes == ["narrow scope"]


async def test_revise_plan_attaches_attempt_number(mock_create: AsyncMock) -> None:
    mock_create.return_value = PlanOutput(
        sub_claims=[SubClaimOutput(id="c1", text="new", rationale="r")],
        overall_rationale="revised",
    )
    previous = [SubClaim(id="c0", text="old", status="pending")]
    event = await plan.revise_plan("Q?", previous, attempt_number=2)
    assert event.attempt_number == 2
    assert event.previous_sub_claims == previous
    assert [c.id for c in event.new_sub_claims] == ["c1"]
    assert event.new_sub_claims[0].status == "pending"


async def test_create_plan_scales_claim_budget_by_question_type(
    mock_create: AsyncMock,
) -> None:
    """Trivial factual questions request a smaller claim budget than
    state-of-the-art ones, so the planner does not over-decompose.
    """
    from app.domain.enums import QuestionType

    mock_create.return_value = PlanOutput(
        sub_claims=[SubClaimOutput(id="c1", text="x", rationale="r")],
        overall_rationale="ok",
    )

    await plan.create_plan("Trivia?", question_type=QuestionType.FACTUAL)
    factual_msg = mock_create.call_args.kwargs["messages"][-1]["content"]
    assert "1-2" in factual_msg

    await plan.create_plan("State?", question_type=QuestionType.STATE_OF_ART)
    state_msg = mock_create.call_args.kwargs["messages"][-1]["content"]
    assert "2-4" in state_msg


def test_claim_budget_defaults_to_middle_range_when_unknown() -> None:
    assert plan._claim_budget(None, None) == (2, 3, 2, 1)


async def test_create_plan_routes_academic_sources_for_state_of_art(
    mock_create: AsyncMock,
) -> None:
    """C5: STATE_OF_ART + STANDARD/DEEP → preferred_sources includes
    semantic_scholar and openalex alongside the web/wiki defaults.
    """
    from app.domain.enums import ComplexityHint, QuestionType

    mock_create.return_value = PlanOutput(
        sub_claims=[SubClaimOutput(id="c1", text="x", rationale="r")],
        overall_rationale="ok",
    )
    event = await plan.create_plan(
        "What is the state of the art in X?",
        question_type=QuestionType.STATE_OF_ART,
        complexity_hint=ComplexityHint.STANDARD,
    )
    assert event.preferred_sources is not None
    assert "semantic_scholar" in event.preferred_sources
    assert "openalex" in event.preferred_sources


async def test_create_plan_routes_academic_sources_for_comparative_deep(
    mock_create: AsyncMock,
) -> None:
    from app.domain.enums import ComplexityHint, QuestionType

    mock_create.return_value = PlanOutput(
        sub_claims=[SubClaimOutput(id="c1", text="x", rationale="r")],
        overall_rationale="ok",
    )
    event = await plan.create_plan(
        "Compare A vs B in depth.",
        question_type=QuestionType.COMPARATIVE,
        complexity_hint=ComplexityHint.DEEP,
    )
    assert event.preferred_sources is not None
    assert "semantic_scholar" in event.preferred_sources
    assert "openalex" in event.preferred_sources


async def test_create_plan_skips_academic_sources_for_factual_trivial(
    mock_create: AsyncMock,
) -> None:
    """C5: trivial factual stays Wikipedia-first; no academic routing."""
    from app.domain.enums import ComplexityHint, QuestionType

    mock_create.return_value = PlanOutput(
        sub_claims=[SubClaimOutput(id="c1", text="x", rationale="r")],
        overall_rationale="ok",
    )
    event = await plan.create_plan(
        "Capital of France?",
        question_type=QuestionType.FACTUAL,
        complexity_hint=ComplexityHint.TRIVIAL,
    )
    assert event.preferred_sources == ["wikipedia"]


async def test_create_plan_realtime_overrides_academic_routing(
    mock_create: AsyncMock,
) -> None:
    """C5: realtime topics need freshness, not citation depth — Tavily only."""
    from app.domain.enums import (
        ComplexityHint,
        QuestionType,
        TemporalSensitivity,
    )

    mock_create.return_value = PlanOutput(
        sub_claims=[SubClaimOutput(id="c1", text="x", rationale="r")],
        overall_rationale="ok",
    )
    event = await plan.create_plan(
        "What is happening right now?",
        question_type=QuestionType.CAUSAL,
        complexity_hint=ComplexityHint.STANDARD,
        temporal_sensitivity=TemporalSensitivity.REALTIME,
    )
    assert event.preferred_sources == ["tavily"]
