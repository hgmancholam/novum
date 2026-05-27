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
