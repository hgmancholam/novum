"""Tests for orchestrator lane routing (IP-25 Phase A).

Verifies that RouteSelectedEvent is emitted after QuestionClassifiedEvent
and before PlanCreated, with correct lane selection.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from app.agent.orchestrator import AgentOrchestrator
from app.agent.run_state import RunState
from app.domain.enums import (
    ComplexityHint,
    Lane,
    QuestionType,
    StopReason,
    TemporalSensitivity,
)
from app.domain.events import (
    BaseEvent,
    PlanCreatedEvent,
    QuestionClassifiedEvent,
    RouteSelectedEvent,
)
from app.llm import client as client_module
from app.llm.models import (
    CritiqueOutput,
    JudgeVerdict,
    PlanOutput,
    QuestionClassification,
    SubClaimOutput,
    SynthesizedAnswer,
)
from app.sources import registry as registry_mod


class _LLMStub:
    """Returns queued responses based on response_model type."""

    def __init__(self) -> None:
        self._queues: dict[str, list[Any]] = {}

    def queue(self, model_name: str, *values: Any) -> None:
        self._queues.setdefault(model_name, []).extend(values)

    async def __call__(self, *_args: Any, **kwargs: Any) -> Any:
        model = kwargs["response_model"]
        name = model.__name__
        # Handle normalization auto-response
        if name == "QuestionNormalization":
            from app.llm.models import QuestionNormalization

            messages = kwargs.get("messages") or []
            user_msg = next(
                (m["content"] for m in messages if m.get("role") == "user"),
                "(stub)",
            )
            return QuestionNormalization(
                normalized_question=user_msg or "(stub)",
                was_corrected=False,
                language="en",
            )
        # Handle synthesizer dict/wrapper redirect
        if name in ("dict", "_RawSynthesizerPayload"):
            queue = self._queues.get("SynthesizedAnswer", [])
            if queue:
                value = queue.pop(0)
                if hasattr(value, "model_dump"):
                    return value.model_dump()
                return value
            raise AssertionError("No queued response for SynthesizedAnswer")
        queue = self._queues.get(name, [])
        if not queue:
            raise AssertionError(f"No queued LLM response for {name}")
        return queue.pop(0)


@pytest.fixture
def llm_stub(monkeypatch: pytest.MonkeyPatch) -> _LLMStub:
    stub = _LLMStub()
    monkeypatch.setattr(client_module.client.chat.completions, "create", stub)
    return stub


@pytest.fixture
def fake_source_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub source registry to avoid actual web requests."""
    from app.seams.source import SourceError

    class _FakeSource:
        def __init__(self, source_type: str):
            self.source_type = source_type

        async def search(self, *_args: Any, **_kwargs: Any) -> list[Any]:
            return []

        async def fetch_full(self, *_args: Any, **_kwargs: Any) -> str:
            raise SourceError("not implemented")

    monkeypatch.setattr(
        registry_mod, "get_source", lambda _: _FakeSource("fake")
    )


@pytest.mark.asyncio
async def test_route_selected_emitted_after_classify(
    llm_stub: _LLMStub, fake_source_registry: None
) -> None:
    """RouteSelectedEvent appears after QuestionClassified and before PlanCreated."""
    # Arrange: queue minimal LLM responses
    llm_stub.queue(
        "QuestionClassification",
        QuestionClassification(
            question_type=QuestionType.COMPARATIVE,
            rationale="Comparing two entities",
            answerable=True,
            confidence=0.92,
            complexity_hint=ComplexityHint.STANDARD,
            heuristic_signals={"word_count": 10},
            temporal_sensitivity=TemporalSensitivity.VOLATILE,
        ),
    )
    llm_stub.queue(
        "PlanOutput",
        PlanOutput(
            sub_claims=[
                SubClaimOutput(id="c1", text="First claim", rationale="Because")
            ],
            overall_rationale="Plan rationale",
            expected_experts=[],
        ),
    )
    # Critique phase
    llm_stub.queue(
        "CritiqueOutput",
        CritiqueOutput(
            acceptable=True,
            summary="Plan looks good",
            issues=[],
            suggested_changes=[],
        ),
    )
    # Synthesizer and judge so the run completes
    llm_stub.queue(
        "SynthesizedAnswer",
        SynthesizedAnswer(
            prose="The answer is 42.",
            key_points=[],
            citations=[],
            gaps=[],
        ),
    )
    llm_stub.queue(
        "JudgeVerdict",
        JudgeVerdict(
            verdict="approve",
            confidence=0.9,
            rationale="Good enough",
            improvements=[],
            factual_errors=[],
            kind_appropriateness=1.0,
        ),
    )
    # Extra synth/judge pair in case the orchestrator runs a second loop
    for _ in range(3):
        llm_stub.queue(
            "SynthesizedAnswer",
            SynthesizedAnswer(
                prose="The answer is 42 (refined).",
                key_points=[],
                citations=[],
                gaps=[],
            ),
        )
        llm_stub.queue(
            "JudgeVerdict",
            JudgeVerdict(
                verdict="approve",
                confidence=0.95,
                rationale="Refined and confirmed",
                improvements=[],
                factual_errors=[],
                kind_appropriateness=1.0,
            ),
        )

    state = RunState(
        run_id=uuid4(),
        question="Compare A and B",
        confidence_threshold=0.7,
    )
    events: list[BaseEvent] = []

    async def emit(event: BaseEvent) -> None:
        events.append(event)

    orch = AgentOrchestrator(state, emit)

    # Act
    result = await orch.run()

    # Assert: run completes
    assert result in {StopReason.JUDGE_CONFIRMED, StopReason.STOPPED_BY_BUDGET}

    # Find the key events
    classified_idx = next(
        i for i, e in enumerate(events) if isinstance(e, QuestionClassifiedEvent)
    )
    route_idx = next(
        (i for i, e in enumerate(events) if isinstance(e, RouteSelectedEvent)), -1
    )
    plan_idx = next(
        i for i, e in enumerate(events) if isinstance(e, PlanCreatedEvent)
    )

    # RouteSelectedEvent must exist
    assert route_idx != -1, "RouteSelectedEvent not emitted"

    # Order: QuestionClassified → RouteSelected → PlanCreated
    assert classified_idx < route_idx < plan_idx

    # Check RouteSelected content
    route_event = events[route_idx]
    assert isinstance(route_event, RouteSelectedEvent)
    assert route_event.lane == Lane.STANDARD
    assert route_event.question_type == QuestionType.COMPARATIVE
    assert route_event.complexity_hint == ComplexityHint.STANDARD
    assert route_event.temporal_sensitivity == TemporalSensitivity.VOLATILE
    assert "STANDARD" in route_event.reason


@pytest.mark.asyncio
async def test_route_selected_emitted_for_trivial_factual(
    llm_stub: _LLMStub, fake_source_registry: None
) -> None:
    """Trivial factual questions route to FAST lane (telemetry only)."""
    llm_stub.queue(
        "QuestionClassification",
        QuestionClassification(
            question_type=QuestionType.FACTUAL,
            rationale="Direct factual question",
            answerable=True,
            confidence=0.95,
            complexity_hint=ComplexityHint.TRIVIAL,
            heuristic_signals={"word_count": 4},
            temporal_sensitivity=TemporalSensitivity.STATIC,
        ),
    )
    llm_stub.queue(
        "PlanOutput",
        PlanOutput(
            sub_claims=[SubClaimOutput(id="c1", text="Claim", rationale="R")],
            overall_rationale="Plan",
            expected_experts=[],
        ),
    )
    llm_stub.queue(
        "SynthesizedAnswer",
        SynthesizedAnswer(
            prose="Tokyo",
            key_points=[],
            citations=[],
            gaps=[],
        ),
    )
    llm_stub.queue(
        "JudgeVerdict",
        JudgeVerdict(
            verdict="approve",
            confidence=1.0,
            rationale="Perfect",
            improvements=[],
            factual_errors=[],
            kind_appropriateness=1.0,
        ),
    )

    state = RunState(run_id=uuid4(), question="What is the capital of Japan?")
    events: list[BaseEvent] = []

    async def emit(event: BaseEvent) -> None:
        events.append(event)

    orch = AgentOrchestrator(state, emit)
    await orch.run()

    # Find RouteSelectedEvent
    route_event = next(
        (e for e in events if isinstance(e, RouteSelectedEvent)), None
    )
    assert route_event is not None
    assert route_event.lane == Lane.FAST
    assert "FAST" in route_event.reason


@pytest.mark.asyncio
async def test_route_selected_emitted_for_deep_causal(
    llm_stub: _LLMStub,
    fake_source_registry: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Causal questions with STANDARD complexity route to DEEP lane."""
    # IP-25 Phase E: stub out the DEEP lane executor so this test stays scoped
    # to its original intent (verifying RouteSelectedEvent emission). Full DEEP
    # lane behavior is covered by tests/test_agent_lanes_deep.py.
    from app.domain.enums import StopReason

    async def _stub_deep_lane(_state: object, _emit: object) -> StopReason:
        return StopReason.JUDGE_CONFIRMED

    monkeypatch.setattr(
        "app.agent.lanes.deep.execute_deep_lane", _stub_deep_lane
    )

    llm_stub.queue(
        "QuestionClassification",
        QuestionClassification(
            question_type=QuestionType.CAUSAL,
            rationale="Exploring causal relationship",
            answerable=True,
            confidence=0.88,
            complexity_hint=ComplexityHint.STANDARD,
            heuristic_signals={"word_count": 15},
            temporal_sensitivity=None,
        ),
    )
    llm_stub.queue(
        "PlanOutput",
        PlanOutput(
            sub_claims=[SubClaimOutput(id="c1", text="Claim", rationale="R")],
            overall_rationale="Plan",
            expected_experts=[],
        ),
    )
    llm_stub.queue(
        "SynthesizedAnswer",
        SynthesizedAnswer(
            prose="Because X causes Y.",
            key_points=[],
            citations=[],
            gaps=[],
        ),
    )
    llm_stub.queue(
        "JudgeVerdict",
        JudgeVerdict(
            verdict="approve",
            confidence=0.8,
            rationale="Acceptable",
            improvements=[],
            factual_errors=[],
            kind_appropriateness=1.0,
        ),
    )

    state = RunState(run_id=uuid4(), question="Why does X cause Y?")
    events: list[BaseEvent] = []

    async def emit(event: BaseEvent) -> None:
        events.append(event)

    orch = AgentOrchestrator(state, emit)
    await orch.run()

    # Find RouteSelectedEvent
    route_event = next(
        (e for e in events if isinstance(e, RouteSelectedEvent)), None
    )
    assert route_event is not None
    assert route_event.lane == Lane.DEEP
    assert "DEEP" in route_event.reason
