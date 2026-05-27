"""Tests for ``app.agent.tasks.draft``."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.agent.run_state import EvidenceItem, RunState
from app.agent.tasks import draft as draft_mod
from app.domain.events import SubClaim
from app.llm import client as client_module
from app.llm.models import JudgeVerdict, SynthesizedAnswer


@pytest.fixture
def mock_create(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock()
    monkeypatch.setattr(client_module.client.chat.completions, "create", mock)
    return mock


def _state(threshold: float = 0.7) -> RunState:
    s = RunState(
        run_id=uuid4(),
        question="Q?",
        confidence_threshold=threshold,
        sub_claims=[
            SubClaim(id="c1", text="t1", status="covered"),
            SubClaim(id="c2", text="t2", status="covered"),
        ],
    )
    s.covered_claims = ["c1", "c2"]
    s.evidence = [
        EvidenceItem(
            claim_id="c1",
            source_url="https://example.com/1",
            source_title="t",
            text="x",
            polarity="neutral",
            confidence=0.7,
        )
    ]
    return s


async def test_draft_answer_populates_state(mock_create: AsyncMock) -> None:
    mock_create.return_value = SynthesizedAnswer(
        prose="The answer is 42.",
        key_points=["one", "two"],
        citations=["https://example.com/1"],
    )
    state = _state()
    result = await draft_mod.draft_answer(state)
    assert state.draft_answer == "The answer is 42."
    assert state.draft_citations == ["https://example.com/1"]
    assert state.draft_sections is not None
    assert len(state.draft_sections) == 2
    assert result.prose == "The answer is 42."


async def test_evaluate_with_judge_passes_when_above_threshold(
    mock_create: AsyncMock,
) -> None:
    mock_create.return_value = JudgeVerdict(confidence=0.9, verdict="approve", rationale="ok")
    state = _state(threshold=0.5)
    event = await draft_mod.evaluate_with_judge(state)
    assert event.judge_confidence == 0.9
    assert event.structural_confidence == 1.0  # 2/2 covered
    assert event.final_confidence == 0.9
    assert event.passed is True


async def test_evaluate_with_judge_fails_when_below_threshold(
    mock_create: AsyncMock,
) -> None:
    mock_create.return_value = JudgeVerdict(confidence=0.4, verdict="approve", rationale="ok")
    state = _state(threshold=0.7)
    event = await draft_mod.evaluate_with_judge(state)
    assert event.passed is False
    assert event.final_confidence == 0.4


async def test_evaluate_with_judge_fails_when_verdict_reject(
    mock_create: AsyncMock,
) -> None:
    mock_create.return_value = JudgeVerdict(
        confidence=0.95, verdict="reject", rationale="bad", improvements=["fix"]
    )
    state = _state(threshold=0.5)
    event = await draft_mod.evaluate_with_judge(state)
    assert event.passed is False
    assert event.suggested_improvements == ["fix"]


async def test_map_issues_to_claims_filters_invalid_ids(
    mock_create: AsyncMock,
) -> None:
    mock_create.return_value = draft_mod.IssueToClaimMapping(claim_ids=["c1", "c99"])
    claims = [
        SubClaim(id="c1", text="t1", status="covered"),
        SubClaim(id="c2", text="t2", status="covered"),
    ]
    result = await draft_mod.map_issues_to_claims(["fix t1"], claims)
    assert result == ["c1"]


async def test_map_issues_empty_returns_empty(mock_create: AsyncMock) -> None:
    result = await draft_mod.map_issues_to_claims([], [])
    assert result == []
    mock_create.assert_not_called()
