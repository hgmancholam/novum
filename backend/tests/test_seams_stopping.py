"""Tests for ``app.seams.stopping`` (Protocol + dataclasses + enum)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.domain.enums import StopReason
from app.seams.stopping import (
    SignalResult,
    StopContext,
    StoppingSignal,
    StopSignalOutput,
)


def _ctx(**overrides: object) -> StopContext:
    base: dict[str, object] = {
        "coverage": 0.5,
        "agreement": 0.5,
        "diversity": 0.5,
        "no_conflict": 1.0,
        "structural_confidence": 0.5,
        "judge_confidence": None,
        "threshold": 0.7,
        "search_count": 0,
        "max_searches": 20,
        "has_contradictions": False,
        "has_ambiguity": False,
        "uncoverable_claims": 0,
        "covered_claims": 0,
        "total_claims": 0,
    }
    base.update(overrides)
    return StopContext(**base)  # type: ignore[arg-type]


def test_signal_result_values() -> None:
    assert SignalResult.CONTINUE.value == "continue"
    assert SignalResult.STOP.value == "stop"
    assert SignalResult.DEFER.value == "defer"
    assert {m.value for m in SignalResult} == {"continue", "stop", "defer"}


def test_stop_signal_output_stop_requires_reason() -> None:
    with pytest.raises(ValueError, match="STOP requires"):
        StopSignalOutput(signal_name="x", result=SignalResult.STOP, stop_reason=None)


def test_stop_signal_output_stop_with_reason_ok() -> None:
    output = StopSignalOutput(
        signal_name="x",
        result=SignalResult.STOP,
        stop_reason=StopReason.JUDGE_CONFIRMED,
    )
    assert output.stop_reason is StopReason.JUDGE_CONFIRMED


def test_stop_signal_output_defer_allows_no_reason() -> None:
    output = StopSignalOutput(signal_name="x", result=SignalResult.DEFER)
    assert output.stop_reason is None


def test_stop_signal_output_continue_allows_no_reason() -> None:
    output = StopSignalOutput(signal_name="x", result=SignalResult.CONTINUE)
    assert output.stop_reason is None


def test_stop_signal_output_frozen() -> None:
    output = StopSignalOutput(signal_name="x", result=SignalResult.CONTINUE)
    with pytest.raises(FrozenInstanceError):
        output.signal_name = "y"  # type: ignore[misc]


def test_stop_context_frozen() -> None:
    ctx = _ctx()
    with pytest.raises(FrozenInstanceError):
        ctx.coverage = 1.0  # type: ignore[misc]


def test_stopping_signal_protocol_runtime_check() -> None:
    class _Minimal:
        name: str = "M"
        priority: int = 100

        async def evaluate(self, context: StopContext) -> StopSignalOutput:
            return StopSignalOutput(signal_name=self.name, result=SignalResult.DEFER)

    assert isinstance(_Minimal(), StoppingSignal)


def test_stopping_signal_protocol_missing_attr_fails() -> None:
    class _BadNoPriority:
        name: str = "Bad"

        async def evaluate(self, context: StopContext) -> StopSignalOutput:
            return StopSignalOutput(signal_name=self.name, result=SignalResult.DEFER)

    assert not isinstance(_BadNoPriority(), StoppingSignal)
