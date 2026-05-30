"""PR-2 Mejora 1.4 — kind-specific payload persistence.

Validates that when the synthesizer returns a typed payload (e.g.
``AnswerKind.WEIGHTED`` with candidates), the StructuredRenderer emits a
typed block instead of regexing the prose. This is the regression test
guarding PR-2 (Mejoras 1.1 -> 1.3).
"""

from __future__ import annotations

from app.domain.enums import AnswerKind
from app.llm.models import (
    ScenarioBranch,
    SynthesizedAnswer,
    TradeoffCriterion,
    WeightedCandidate,
)
from app.output.structured import StructuredRenderer
from app.seams.output import RenderContext


def _ctx(payload: SynthesizedAnswer | None) -> RenderContext:
    return RenderContext(
        question="Q?",
        answer_content=payload.prose if payload else "",
        sources=[],
        confidence=0.7,
        stop_reason="judge_confirmed",
        synth_payload=payload,
    )


def test_weighted_payload_emits_key_value_block() -> None:
    payload = SynthesizedAnswer(
        prose="Comparison summary.",
        answer_kind=AnswerKind.WEIGHTED,
        candidates=[
            WeightedCandidate(label="A", score=0.7, rationale="Better latency"),
            WeightedCandidate(label="B", score=0.3, rationale="Cheaper"),
        ],
    )
    data = StructuredRenderer().build_data(_ctx(payload))
    types = [b.type for b in data.blocks]
    assert "keyValue" in types
    kv = next(b for b in data.blocks if b.type == "keyValue")
    assert kv.title == "Weighted comparison"
    assert any("A" in r.key and "70%" in r.key for r in kv.rows)


def test_scenario_payload_emits_keypoints_per_branch() -> None:
    payload = SynthesizedAnswer(
        prose="Scenario analysis.",
        answer_kind=AnswerKind.SCENARIO,
        scenarios=[
            ScenarioBranch(
                label="Bull",
                probability_band="high",
                summary="Strong adoption",
                drivers=["funding", "regulation"],
            ),
            ScenarioBranch(
                label="Bear",
                probability_band="low",
                summary="Slowdown",
                drivers=["macro"],
            ),
        ],
    )
    data = StructuredRenderer().build_data(_ctx(payload))
    kp_blocks = [
        b
        for b in data.blocks
        if b.type == "keyPoints" and b.title != "Bottom line"
    ]
    assert len(kp_blocks) == 2
    assert kp_blocks[0].title == "Bull (high)"
    assert "Driver: funding" in kp_blocks[0].items


def test_tradeoff_payload_emits_criteria_table() -> None:
    payload = SynthesizedAnswer(
        prose="Tradeoff.",
        answer_kind=AnswerKind.TRADEOFF,
        criteria=[
            TradeoffCriterion(name="cost", weight=0.4, notes="cheap matters"),
            TradeoffCriterion(name="speed", weight=0.6, notes="fast matters more"),
        ],
    )
    data = StructuredRenderer().build_data(_ctx(payload))
    kv = next(b for b in data.blocks if b.type == "keyValue")
    assert kv.title == "Trade-off criteria"
    assert any("speed" in r.key and "60%" in r.key for r in kv.rows)


def test_best_effort_payload_emits_interpretation_paragraph_first() -> None:
    payload = SynthesizedAnswer(
        prose="Some prose.",
        answer_kind=AnswerKind.BEST_EFFORT,
        interpretation="user likely asks about X",
        alternative_interpretations=["maybe Y", "maybe Z"],
    )
    data = StructuredRenderer().build_data(_ctx(payload))
    # IP-32 UX: a Bottom Line keyPoints block is prepended when prose is
    # non-empty. The interpretation paragraph is the first kind-specific
    # block (i.e. blocks[1]).
    assert data.blocks[0].type == "keyPoints"
    assert data.blocks[0].title == "Bottom line"
    assert data.blocks[1].type == "paragraph"
    assert "Most likely interpretation" in data.blocks[1].text
    assert any(
        b.type == "keyPoints" and "maybe Y" in b.items for b in data.blocks
    )


def test_no_payload_keeps_legacy_pipeline() -> None:
    data = StructuredRenderer().build_data(
        RenderContext(
            question="Q?",
            answer_content="Just a single paragraph.",
            sources=[],
            confidence=0.5,
            stop_reason="judge_confirmed",
            synth_payload=None,
        )
    )
    # IP-32 UX: the first block is the Bottom Line headline.
    assert data.blocks[0].type == "keyPoints"
    assert data.blocks[0].title == "Bottom line"
    assert all(
        b.type in {"paragraph", "markdown", "keyPoints"} for b in data.blocks
    )
