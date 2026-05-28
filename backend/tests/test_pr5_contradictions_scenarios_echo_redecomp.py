"""PR-5 — Mejoras 7.1, 7.2, 8.1, 8.2.

Covers:
- 7.1: contradictions surface in structured render.
- 7.2: ScenarioBranch.assumptions surface in scenario block; field is
  backward-compatible (defaults to []).
- 8.1: echo-chamber penalty fires under widened thresholds (agreement >= 0.9,
  window < 14 days).
- 8.2: re-decomposition buffer widens to +0.20 on the first round.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.agent.orchestrator import AgentOrchestrator
from app.agent.run_state import EvidenceItem, RunState
from app.agent.states import AgentState
from app.confidence.structural import apply_echo_chamber_penalty
from app.domain.enums import AnswerKind, AuthorityTier, QuestionType
from app.domain.events import PlanGapsDetectedEvent, SubClaim
from app.domain.structured import KeyPointsBlock
from app.llm.models import ScenarioBranch, SynthesizedAnswer
from app.output.structured import StructuredRenderer
from app.seams.output import RenderContext


def _ctx(payload: SynthesizedAnswer | None, text: str = "") -> RenderContext:
    return RenderContext(
        question="q",
        answer_content=text,
        confidence=0.8,
        sources=[],
        stop_reason="judge_confirmed",
        synth_payload=payload,
    )


# ----------------------------------------------------------------------
# Mejora 7.1 — contradictions block
# ----------------------------------------------------------------------


def test_contradictions_render_as_keypoints_block_first() -> None:
    payload = SynthesizedAnswer(
        answer_kind=AnswerKind.BEST_EFFORT,
        prose="x",
        interpretation="y",
        contradictions=["A says X, B says not-X", "Date conflict on launch"],
    )
    data = StructuredRenderer().build_data(_ctx(payload))
    kp = [b for b in data.blocks if isinstance(b, KeyPointsBlock)]
    assert kp, "expected at least one KeyPointsBlock"
    assert kp[0].title == "Contradictions detected"
    assert kp[0].items == [
        "A says X, B says not-X",
        "Date conflict on launch",
    ]


def test_no_contradictions_block_when_empty() -> None:
    payload = SynthesizedAnswer(
        answer_kind=AnswerKind.BEST_EFFORT,
        prose="x",
        interpretation="y",
        contradictions=None,
    )
    data = StructuredRenderer().build_data(_ctx(payload))
    titles = [
        b.title for b in data.blocks if isinstance(b, KeyPointsBlock)
    ]
    assert "Contradictions detected" not in titles


# ----------------------------------------------------------------------
# Mejora 7.2 — ScenarioBranch.assumptions
# ----------------------------------------------------------------------


def test_scenario_branch_assumptions_default_empty_back_compat() -> None:
    # Old payload without `assumptions` MUST still validate.
    s = ScenarioBranch(
        label="Base",
        probability_band="medium",
        summary="s",
        drivers=["d1", "d2"],
    )
    assert s.assumptions == []


def test_scenario_block_includes_assumption_lines() -> None:
    payload = SynthesizedAnswer(
        answer_kind=AnswerKind.SCENARIO,
        prose="x",
        scenarios=[
            ScenarioBranch(
                label="Optimistic",
                probability_band="high",
                summary="growth continues",
                drivers=["demand up", "supply stable"],
                assumptions=["no recession", "no policy shock"],
            )
        ],
    )
    data = StructuredRenderer().build_data(_ctx(payload))
    kp = [
        b
        for b in data.blocks
        if isinstance(b, KeyPointsBlock) and b.title.startswith("Optimistic")
    ]
    assert kp, "expected a scenario KeyPointsBlock"
    items = kp[0].items
    assert "Driver: demand up" in items
    assert "Driver: supply stable" in items
    assert "Assumption: no recession" in items
    assert "Assumption: no policy shock" in items


# ----------------------------------------------------------------------
# Mejora 8.1 — echo-chamber thresholds
# ----------------------------------------------------------------------


def _evidence(claim_id: str, dates: list[datetime], polarities: list[str]) -> list[EvidenceItem]:
    return [
        EvidenceItem(
            claim_id=claim_id,
            source_url=f"https://x{i}.com",
            source_title=f"S{i}",
            text="t",
            polarity=p,
            confidence=0.8,
            source_published_date=d,
            authority_tier=AuthorityTier.REPUTABLE_SECONDARY,
        )
        for i, (d, p) in enumerate(zip(dates, polarities, strict=True))
    ]


def _make_state(evidence: list[EvidenceItem]) -> RunState:
    state = RunState(
        run_id=uuid4(),
        question="q",
        question_type=QuestionType.FACTUAL,
        confidence_threshold=0.7,
        max_searches=10,
    )
    state.sub_claims = [SubClaim(id="c1", text="claim", status="covered")]
    state.evidence = evidence
    return state


def test_echo_chamber_fires_when_window_is_twelve_days() -> None:
    base = datetime(2025, 1, 1, 12, 0, 0)
    evidence = _evidence(
        "c1",
        [base, base + timedelta(days=6), base + timedelta(days=12)],
        ["supports", "supports", "supports"],
    )
    state = _make_state(evidence)
    _, event = apply_echo_chamber_penalty(state, 1.0)
    assert event is not None, "12-day window must trigger penalty under 8.1"
    assert event.date_window_days == 12


def test_echo_chamber_fires_when_agreement_is_ninety_percent() -> None:
    # 9 supports + 1 contradicts → agreement ~0.9 ≥ 0.9 threshold.
    base = datetime(2025, 1, 1, 12, 0, 0)
    dates = [base + timedelta(days=i) for i in range(10)]
    polarities = ["supports"] * 9 + ["contradicts"]
    evidence = _evidence("c1", dates, polarities)
    state = _make_state(evidence)
    _, event = apply_echo_chamber_penalty(state, 1.0)
    assert event is not None, "agreement ≥ 0.9 must trigger under 8.1"


def test_echo_chamber_still_skipped_above_fourteen_days() -> None:
    base = datetime(2025, 1, 1, 12, 0, 0)
    evidence = _evidence(
        "c1",
        [base, base + timedelta(days=10), base + timedelta(days=20)],
        ["supports", "supports", "supports"],
    )
    state = _make_state(evidence)
    _, event = apply_echo_chamber_penalty(state, 1.0)
    assert event is None


# ----------------------------------------------------------------------
# Mejora 8.2 — first-round redecomposition buffer widened to +0.20
# ----------------------------------------------------------------------


@pytest.fixture
def redecomp_state() -> RunState:
    state = RunState(
        run_id=uuid4(),
        question="q",
        question_type=QuestionType.CAUSAL,
        confidence_threshold=0.7,
        max_searches=10,
    )
    state.sub_claims = [
        SubClaim(id="c1", text="a", status="covered"),
        SubClaim(id="c2", text="b", status="covered"),
    ]
    state.current_state = AgentState.ANALYZING
    state.search_count = 2
    state.redecomposition_count = 0
    state.max_redecomposition = 1
    return state


@pytest.mark.asyncio
async def test_first_redecomp_fires_in_widened_band(redecomp_state: RunState) -> None:
    # S=0.85, threshold=0.7 → +0.15 above. Old code (buffer=0.10) would skip;
    # PR-5 (buffer=0.20 on first round) must trigger.
    events: list[object] = []

    async def emit(e: object) -> None:
        events.append(e)

    with (
        patch("app.agent.orchestrator.analyze_evidence", new_callable=AsyncMock) as ma,
        patch("app.confidence.calculate_structural_confidence") as mc,
        patch("app.agent.tasks.replan.identify_plan_gaps", new_callable=AsyncMock) as mg,
    ):
        ma.return_value = []
        conf = AsyncMock()
        conf.score = 0.85
        mc.return_value = conf
        mg.return_value = ["gap"]

        orch = AgentOrchestrator(redecomp_state, emit=emit)
        await orch._handle_analyzing()

    assert any(isinstance(e, PlanGapsDetectedEvent) for e in events)
    assert redecomp_state.redecomposition_count == 1


@pytest.mark.asyncio
async def test_second_redecomp_keeps_tight_band(redecomp_state: RunState) -> None:
    # After 1 redecomp, buffer reverts to 0.10. S=0.85 should NOT trigger.
    redecomp_state.redecomposition_count = 1
    redecomp_state.max_redecomposition = 2
    events: list[object] = []

    async def emit(e: object) -> None:
        events.append(e)

    with (
        patch("app.agent.orchestrator.analyze_evidence", new_callable=AsyncMock) as ma,
        patch("app.confidence.calculate_structural_confidence") as mc,
        patch("app.agent.tasks.replan.identify_plan_gaps", new_callable=AsyncMock) as mg,
    ):
        ma.return_value = []
        conf = AsyncMock()
        conf.score = 0.85
        mc.return_value = conf

        orch = AgentOrchestrator(redecomp_state, emit=emit)
        await orch._handle_analyzing()

    mg.assert_not_awaited()
    assert redecomp_state.redecomposition_count == 1
