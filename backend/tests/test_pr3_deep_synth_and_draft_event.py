"""PR-3 (Mejoras 3.1 + 3.2): DEEP-lane deep synthesis prompts + DraftSynthesized event.

3.1 — DEEP synthesis must route through ``build_synthesizer_prompt`` (the same
      kind-aware pipeline STANDARD uses) instead of the FAST minimalist prompt.
3.2 — Every synthesis path (FAST/STANDARD/DEEP/CoVe) emits a
      ``DraftSynthesizedEvent`` so the event log preserves the draft + the
      resolver-chosen ``answer_kind`` independently of the eventual
      ``JudgeRuled`` / ``Stopped`` events (RF-03).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.agent.lanes.deep import (
    _select_deep_answer_kind,
    _synthesize_with_contradictions,
    _synthesize_with_react_history,
)
from app.agent.run_state import RunState
from app.domain.enums import AnswerKind, Lane, QuestionType
from app.domain.events import DraftSynthesizedEvent
from app.domain.hypothesis import Hypothesis
from app.llm.models import (
    ScenarioBranch,
    SynthesizedAnswer,
    WeightedCandidate,
)


def _make_state(
    *,
    question_type: QuestionType = QuestionType.STATE_OF_ART,
    hypotheses: list[Hypothesis] | None = None,
    structural: float = 0.6,
    ambiguity: bool = False,
) -> RunState:
    state = RunState(
        run_id=uuid4(),
        question="¿Qué causó la caída del Imperio Romano?",
        owner_username="tester",
        question_type=question_type,
        selected_lane=Lane.DEEP,
    )
    state.hypotheses = hypotheses or []
    state.last_structural_confidence = structural
    state.has_ambiguity = ambiguity
    return state


# ---------------------------------------------------------------------------
# Mejora 3.1 — kind resolver + build_synthesizer_prompt
# ---------------------------------------------------------------------------


def test_select_deep_answer_kind_predictive_routes_to_scenario() -> None:
    """PREDICTIVE_FUTURE always lands on SCENARIO per §0.8 row 3."""
    state = _make_state(
        question_type=QuestionType.PREDICTIVE_FUTURE,
        hypotheses=[
            Hypothesis(text="A", priority=0.6, verdict="confirmed"),
            Hypothesis(text="B", priority=0.5, verdict="confirmed"),
        ],
    )
    assert _select_deep_answer_kind(state) == AnswerKind.SCENARIO


def test_select_deep_answer_kind_falls_to_best_effort_when_ambiguous() -> None:
    state = _make_state(ambiguity=True)
    assert _select_deep_answer_kind(state) == AnswerKind.BEST_EFFORT


def test_select_deep_answer_kind_contradictions_lower_agreement() -> None:
    """With contradictions present and full coverage, resolver picks WEIGHTED."""
    state = _make_state(
        question_type=QuestionType.STATE_OF_ART,
        hypotheses=[Hypothesis(text="X", priority=0.7, verdict="confirmed")],
        structural=0.9,
    )
    assert (
        _select_deep_answer_kind(state, contradictions_present=True)
        == AnswerKind.WEIGHTED
    )


@pytest.mark.asyncio
async def test_synthesize_with_react_history_uses_build_synthesizer_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DEEP synthesis must call build_synthesizer_prompt (not FAST prompt)."""
    state = _make_state(
        question_type=QuestionType.PREDICTIVE_FUTURE,
        hypotheses=[Hypothesis(text="H1", priority=0.9, verdict="confirmed")],
    )

    captured: dict = {}

    def fake_builder(*, question, evidence, answer_kind, user_language, **kwargs):
        captured["question"] = question
        captured["answer_kind"] = answer_kind
        captured["evidence"] = evidence
        captured["language"] = user_language
        captured["hypotheses"] = kwargs.get("hypotheses")
        return ("FAKE_SYSTEM_PROMPT", 600)

    monkeypatch.setattr(
        "app.llm.prompts.build_synthesizer_prompt", fake_builder
    )

    async def fake_llm_call(role, messages, response_model, **kwargs):
        # The system prompt must come from the kind-aware builder.
        assert messages[0]["content"] == "FAKE_SYSTEM_PROMPT"
        return SynthesizedAnswer(
            prose="Two plausible scenarios diverge based on policy choices.",
            scenarios=[
                ScenarioBranch(
                    label="Optimistic",
                    probability_band="high",
                    summary="Reform succeeds",
                    drivers=["Driver A"],
                ),
                ScenarioBranch(
                    label="Pessimistic",
                    probability_band="medium",
                    summary="Reform stalls",
                    drivers=["Driver B"],
                ),
            ],
            answer_kind=AnswerKind.SCENARIO,
        )

    monkeypatch.setattr("app.agent.lanes.deep.llm.call", fake_llm_call)

    result = await _synthesize_with_react_history(state)

    assert captured["answer_kind"] == AnswerKind.SCENARIO
    assert captured["language"] == "es"
    assert captured["hypotheses"] == [{"text": "H1", "priority": 0.9}]
    assert result.answer_kind == AnswerKind.SCENARIO


@pytest.mark.asyncio
async def test_synthesize_with_contradictions_passes_requires_contradictions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _make_state(
        question_type=QuestionType.STATE_OF_ART,
        hypotheses=[Hypothesis(text="H1", priority=0.7, verdict="confirmed")],
        structural=0.9,
    )

    captured: dict = {}

    def fake_builder(*, question, evidence, answer_kind, user_language, **kwargs):
        captured["requires_contradictions"] = kwargs.get(
            "requires_contradictions"
        )
        captured["evidence_titles"] = [e["title"] for e in evidence]
        captured["answer_kind"] = answer_kind
        return ("SYS", 700)

    monkeypatch.setattr(
        "app.llm.prompts.build_synthesizer_prompt", fake_builder
    )

    async def fake_llm_call(role, messages, response_model, **kwargs):
        return SynthesizedAnswer(
            prose="Revised draft addressing the contradiction.",
            candidates=[
                WeightedCandidate(
                    label="Option A", score=0.7, rationale="solid evidence"
                ),
                WeightedCandidate(
                    label="Option B", score=0.5, rationale="some evidence"
                ),
            ],
            answer_kind=AnswerKind.WEIGHTED,
            contradictions=["Some contradiction"],
        )

    monkeypatch.setattr("app.agent.lanes.deep.llm.call", fake_llm_call)

    result = await _synthesize_with_contradictions(
        state, "Contradicting evidence body"
    )

    assert captured["requires_contradictions"] is True
    assert "Verification contradictions" in captured["evidence_titles"]
    assert result.answer_kind == AnswerKind.WEIGHTED


# ---------------------------------------------------------------------------
# Mejora 3.2 — DraftSynthesizedEvent emission
# ---------------------------------------------------------------------------


def test_draft_synthesized_event_round_trips_in_event_map() -> None:
    """Event type registered in EVENT_TYPE_MAP and discriminated union."""
    from app.domain.enums import EventType
    from app.domain.events import EVENT_TYPE_MAP

    assert EventType.DRAFT_SYNTHESIZED in EVENT_TYPE_MAP
    assert EVENT_TYPE_MAP[EventType.DRAFT_SYNTHESIZED] is DraftSynthesizedEvent

    event = DraftSynthesizedEvent(
        prose="draft prose",
        answer_kind=AnswerKind.DIRECT,
        citation_count=2,
        key_point_count=3,
        source="standard",
    )
    dumped = event.model_dump()
    assert dumped["type"] == "DraftSynthesized"
    assert dumped["answer_kind"] == "direct"
    assert dumped["source"] == "standard"


@pytest.mark.asyncio
async def test_standard_lane_emits_draft_synthesized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Orchestrator._handle_drafting emits DraftSynthesizedEvent."""
    from app.agent.orchestrator import AgentOrchestrator
    from app.agent.states import AgentState

    # Build a minimal orchestrator with a stub state + emit recorder.
    state = _make_state()
    state.current_state = AgentState.DRAFTING

    events: list = []

    async def fake_draft(_state):
        _state.draft_payload = SynthesizedAnswer(
            prose="Standard draft prose.",
            key_points=["k1", "k2"],
            citations=["http://a", "http://b"],
            answer_kind=AnswerKind.DIRECT,
        )
        return _state.draft_payload

    monkeypatch.setattr(
        "app.agent.orchestrator.draft_answer", fake_draft
    )

    # Build orchestrator with bare minimum (we only call _handle_drafting).
    orch = AgentOrchestrator.__new__(AgentOrchestrator)
    orch.state = state  # type: ignore[attr-defined]

    async def emit(event):
        events.append(event)

    orch.emit = emit  # type: ignore[attr-defined]

    await orch._handle_drafting()

    drafts = [e for e in events if isinstance(e, DraftSynthesizedEvent)]
    assert len(drafts) == 1
    assert drafts[0].source == "standard"
    assert drafts[0].answer_kind == AnswerKind.DIRECT
    assert drafts[0].citation_count == 2
    assert drafts[0].key_point_count == 2
    assert state.current_state == AgentState.JUDGING
