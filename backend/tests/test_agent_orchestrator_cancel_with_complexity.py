"""Tests for RF-08 cancellation preservation with complexity features (BRD-22).

Covers:
- Cancel during trivial path before SEARCHING → user_cancelled, no PlanCritiquedEvent
- Cancel during deep path after first critique but before second → user_cancelled
- Cancel during instant cache replay window → user_cancelled wins, no synthetic events
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.agent.instant_cache import CachedRun, record_run, reset_instant_cache
from app.agent.orchestrator import AgentOrchestrator
from app.agent.run_state import RunState
from app.domain.enums import (
    AnswerKind,
    StopReason,
)
from app.domain.events import BaseEvent
from app.llm import client as client_module
from app.llm.models import PlanOutput, QuestionClassification, SubClaimOutput


class YieldingEmitHook:
    """Yielding emit hook for L-010 cancellation tests."""

    def __init__(self) -> None:
        self.events: list[BaseEvent] = []
        self._cancel_at: str | None = None
        self._orch: AgentOrchestrator | None = None

    def set_cancel_at(self, event_type: str, orch: AgentOrchestrator) -> None:
        self._cancel_at = event_type
        self._orch = orch

    async def __call__(self, event: BaseEvent) -> None:
        self.events.append(event)
        # Yield control so orchestrator can observe cancellation
        await asyncio.sleep(0)
        if self._cancel_at == event.type and self._orch is not None:
            self._orch.cancel()


@pytest.fixture
def mock_llm(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock()
    monkeypatch.setattr(client_module.client.chat.completions, "create", mock)
    return mock


@pytest.fixture(autouse=True)
def _stub_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid real embedding calls (saturation signal + planner similarity).

    Same rationale as test_agent_orchestrator.py: real litellm dials out
    under tenacity retries and looks like a multi-minute hang.
    """
    import numpy as np

    from app.llm import embeddings as embeddings_module
    from app.stopping.signals import saturation as saturation_module

    async def _fake_embed(texts: list[str], *, model: str | None = None) -> list[np.ndarray]:
        return [np.zeros(1536, dtype=np.float32) for _ in texts]

    monkeypatch.setattr(embeddings_module, "embed", _fake_embed)
    monkeypatch.setattr(saturation_module, "embed", _fake_embed)


@pytest.mark.asyncio
async def test_cancel_during_trivial_path_before_searching(mock_llm: AsyncMock) -> None:
    """Cancel during trivial path (after PlanCreated, before SEARCHING) → user_cancelled."""
    # Mock classifier: factual + trivial hint
    mock_llm.side_effect = [
        # QuestionNormalization
        type("Obj", (), {"normalized_question": "Tokyo?", "was_corrected": False, "language": "en"})(),
        # QuestionClassification
        QuestionClassification(
            question_type="factual",
            rationale="trivial",
            answerable=True,
            confidence=0.95,
        ),
        # PlanOutput
        PlanOutput(
            sub_claims=[SubClaimOutput(id="c1", text="claim", rationale="r")],
            overall_rationale="trivial plan",
            expected_experts=[],
        ),
    ]

    state = RunState(
        run_id=uuid4(),
        question="Capital of Japan?",
        owner_username="testuser",
    )
    emit_hook = YieldingEmitHook()
    orch = AgentOrchestrator(state, emit_hook)

    # Cancel right after PlanCreated
    emit_hook.set_cancel_at("PlanCreated", orch)

    stop_reason = await orch.run()

    # Verify user_cancelled
    assert stop_reason == StopReason.USER_CANCELLED

    event_types = [e.type for e in emit_hook.events]
    assert "QuestionAsked" in event_types
    assert "PlanCreated" in event_types
    # trivial → critique_passes_target=0, so no PlanCritiqued
    assert "PlanCritiqued" not in event_types
    assert "Stopped" in event_types


@pytest.mark.asyncio
async def test_cancel_during_deep_path_mid_critique(
    mock_llm: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cancel during deep path after first critique but before second → user_cancelled."""
    # Force STANDARD lane so the planning/critique pipeline runs. The original
    # "deep path" here refers to the legacy multi-critique pipeline, NOT the
    # Phase E DEEP lane (which has its own ReAct loop tested separately).
    from app.domain.enums import Lane

    monkeypatch.setattr(
        "app.agent.lane_router.select_lane",
        lambda *_a, **_kw: (Lane.STANDARD, "test_forced_standard"),
    )

    # Mock classifier: state_of_art + deep hint
    mock_llm.side_effect = [
        # QuestionNormalization
        type("Obj", (), {"normalized_question": "Long research question?", "was_corrected": False, "language": "en"})(),
        # QuestionClassification
        QuestionClassification(
            question_type="state_of_art",
            rationale="deep",
            answerable=True,
            confidence=0.50,
        ),
        # PlanOutput
        PlanOutput(
            sub_claims=[SubClaimOutput(id="c1", text="claim", rationale="r")],
            overall_rationale="deep plan",
            expected_experts=[],
        ),
        # First critique
        type("Obj", (), {"acceptable": False, "summary": "needs work", "issues": ["x"], "suggested_changes": ["y"]})(),
    ]

    state = RunState(
        run_id=uuid4(),
        question="What are the latest advances?",
        owner_username="testuser",
    )
    emit_hook = YieldingEmitHook()
    orch = AgentOrchestrator(state, emit_hook)

    # Cancel right after first PlanCritiqued
    emit_hook.set_cancel_at("PlanCritiqued", orch)

    stop_reason = await orch.run()

    assert stop_reason == StopReason.USER_CANCELLED

    event_types = [e.type for e in emit_hook.events]
    assert "PlanCreated" in event_types
    assert "PlanCritiqued" in event_types
    # Cancelled before second critique
    assert event_types.count("PlanCritiqued") == 1
    assert "Stopped" in event_types


@pytest.mark.asyncio
async def test_cancel_during_instant_cache_replay_window(mock_llm: AsyncMock) -> None:
    """Cancel during instant cache replay window → user_cancelled wins, no synthetic events."""
    reset_instant_cache()

    # Record a cached run
    cached = CachedRun(
        run_id=uuid4(),
        final_confidence=0.90,
        judge_confidence=0.88,
        structural_confidence=0.92,
        stop_reason=StopReason.JUDGE_CONFIRMED,
        answer_kind=AnswerKind.DIRECT,
        answer_prose="Tokyo",
        answer_structured=None,
        answer_structured_data=None,
        citations=[],
        completed_at=datetime.now(UTC),
    )
    record_run("testuser", "Capital of Japan?", cached)

    state = RunState(
        run_id=uuid4(),
        question="Capital of Japan?",
        owner_username="testuser",
    )
    emit_hook = YieldingEmitHook()
    orch = AgentOrchestrator(state, emit_hook)

    # Cancel right after QuestionAsked (before instant replay can complete)
    emit_hook.set_cancel_at("QuestionAsked", orch)

    stop_reason = await orch.run()

    # Cancel wins over instant replay
    assert stop_reason == StopReason.USER_CANCELLED

    event_types = [e.type for e in emit_hook.events]
    # Replay events (PriorRunHintReplayed, synthetic JudgeRuled) should NOT be emitted
    assert "PriorRunHintReplayed" not in event_types
    # Only QuestionAsked + Stopped with user_cancelled
    assert "QuestionAsked" in event_types
    assert "Stopped" in event_types
