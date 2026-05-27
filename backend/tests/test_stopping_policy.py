"""Integration tests for ``StoppingPolicy`` (coordinator + signal interplay)."""

from __future__ import annotations

import logging
from uuid import uuid4

import pytest
import structlog

from app.agent.run_state import EvidenceItem, RunState
from app.domain.enums import StopReason
from app.domain.events import SubClaim
from app.seams.stopping import (
    SignalResult,
    StopContext,
    StoppingSignal,
    StopSignalOutput,
)
from app.stopping import (
    AgreementSignal,
    BudgetSignal,
    CoverageSignal,
    HonestStopSignal,
    JudgeSignal,
    StoppingPolicy,
)


def _state(**overrides: object) -> RunState:
    defaults: dict[str, object] = {
        "run_id": uuid4(),
        "question": "Q?",
        "confidence_threshold": 0.7,
        "max_searches": 20,
        "search_count": 0,
        "sub_claims": [],
    }
    defaults.update(overrides)
    return RunState(**defaults)  # type: ignore[arg-type]


def _evidence(claim_id: str = "c1", url: str = "http://a.example", polarity: str = "supports") -> EvidenceItem:
    return EvidenceItem(
        claim_id=claim_id,
        source_url=url,
        source_title="t",
        text="snippet",
        polarity=polarity,
        confidence=1.0,
    )


# ---------------------------------------------------------------------------
# Recording fake signal
# ---------------------------------------------------------------------------


class _RecordingFake:
    """Fake signal that records every context it sees."""

    name: str = "Recorder"

    def __init__(self, priority: int = 50, result: SignalResult = SignalResult.DEFER) -> None:
        self.priority = priority
        self._result = result
        self.seen: list[StopContext] = []

    async def evaluate(self, context: StopContext) -> StopSignalOutput:
        self.seen.append(context)
        return StopSignalOutput(signal_name=self.name, result=self._result)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_policy_default_signal_order() -> None:
    policy = StoppingPolicy()
    names = [s.name for s in policy.signals]
    assert names == ["HonestStop", "Budget", "Coverage", "Agreement", "Judge"]
    priorities = [s.priority for s in policy.signals]
    assert priorities == sorted(priorities)


def test_policy_custom_signal_set() -> None:
    policy = StoppingPolicy(signals=[BudgetSignal()])
    assert [s.name for s in policy.signals] == ["Budget"]


def test_policy_signals_property_is_tuple() -> None:
    policy = StoppingPolicy()
    assert isinstance(policy.signals, tuple)


async def test_policy_honest_fires_before_budget() -> None:
    """WP-3: HonestStopSignal is deprecated (no STOP), so Budget wins when over budget."""
    state = _state(
        max_searches=5,
        search_count=10,  # over budget
        sub_claims=[SubClaim(id="c1", text="t", status="pending")],
    )
    state.contradictions.append(object())  # type: ignore[arg-type]
    state.evidence.append(_evidence(polarity="contradicts"))

    policy = StoppingPolicy()
    result = await policy.evaluate(state)

    assert result.result is SignalResult.STOP
    assert result.stop_reason is StopReason.STOPPED_BY_BUDGET


async def test_policy_budget_fires_before_judge() -> None:
    """Budget (priority 20) stops before Judge (priority 40) even on a passing run."""
    state = _state(
        max_searches=5,
        search_count=5,
        sub_claims=[SubClaim(id="c1", text="t", status="covered")],
        covered_claims=["c1"],
    )
    state.evidence.append(_evidence())

    policy = StoppingPolicy()
    result = await policy.evaluate(state, judge_confidence=0.95)

    assert result.result is SignalResult.STOP
    assert result.stop_reason is StopReason.STOPPED_BY_BUDGET


async def test_policy_judge_confirmation_full_path() -> None:
    state = _state(
        max_searches=20,
        search_count=2,
        confidence_threshold=0.7,
        sub_claims=[
            SubClaim(id=f"c{i}", text="t", status="covered") for i in range(1, 6)
        ],
        covered_claims=[f"c{i}" for i in range(1, 6)],
    )
    # 4 distinct domains → diversity 0.9; all supporting → agreement 1.0.
    state.evidence.extend(
        [
            _evidence(url="http://a.example"),
            _evidence(url="http://b.example"),
            _evidence(url="http://c.example"),
            _evidence(url="http://d.example"),
        ]
    )

    policy = StoppingPolicy()
    result = await policy.evaluate(state, judge_confidence=0.9)

    assert result.result is SignalResult.STOP
    assert result.stop_reason is StopReason.JUDGE_CONFIRMED


async def test_policy_continue_when_everyone_defers_or_continues() -> None:
    state = _state(
        max_searches=20,
        search_count=2,
        sub_claims=[SubClaim(id="c1", text="t", status="pending")],
    )
    policy = StoppingPolicy()
    result = await policy.evaluate(state)  # no judge yet
    assert result.result is SignalResult.CONTINUE


async def test_policy_continue_when_all_defer() -> None:
    """If every signal defers, the overall policy result is CONTINUE."""
    defer_only = _RecordingFake(priority=1, result=SignalResult.DEFER)
    policy = StoppingPolicy(signals=[defer_only])
    state = _state(sub_claims=[SubClaim(id="c1", text="t", status="pending")])
    result = await policy.evaluate(state)
    assert result.result is SignalResult.CONTINUE
    assert result.signal_name == "StoppingPolicy"


def test_policy_should_stop_helper() -> None:
    stop_out = StopSignalOutput(
        signal_name="x",
        result=SignalResult.STOP,
        stop_reason=StopReason.JUDGE_CONFIRMED,
    )
    cont_out = StopSignalOutput(signal_name="x", result=SignalResult.CONTINUE)
    defer_out = StopSignalOutput(signal_name="x", result=SignalResult.DEFER)
    assert StoppingPolicy.should_stop(stop_out) is True
    assert StoppingPolicy.should_stop(cont_out) is False
    assert StoppingPolicy.should_stop(defer_out) is False


async def test_policy_uses_structural_confidence_once() -> None:
    """All signals see the SAME structural_confidence value (computed once)."""
    fake_a = _RecordingFake(priority=1, result=SignalResult.DEFER)
    fake_b = _RecordingFake(priority=2, result=SignalResult.DEFER)
    fake_c = _RecordingFake(priority=3, result=SignalResult.DEFER)
    policy = StoppingPolicy(signals=[fake_a, fake_b, fake_c])

    state = _state(
        sub_claims=[
            SubClaim(id=f"c{i}", text="t", status="covered") for i in range(1, 4)
        ],
        covered_claims=["c1", "c2", "c3"],
    )
    state.evidence.extend(
        [
            _evidence(url="http://a.example"),
            _evidence(url="http://b.example"),
        ]
    )

    await policy.evaluate(state, judge_confidence=0.8)

    assert len(fake_a.seen) == 1
    assert len(fake_b.seen) == 1
    assert len(fake_c.seen) == 1
    s_values = {
        fake_a.seen[0].structural_confidence,
        fake_b.seen[0].structural_confidence,
        fake_c.seen[0].structural_confidence,
    }
    assert len(s_values) == 1
    j_values = {
        fake_a.seen[0].judge_confidence,
        fake_b.seen[0].judge_confidence,
        fake_c.seen[0].judge_confidence,
    }
    assert j_values == {0.8}


async def test_policy_evaluate_signals_sorted_by_priority() -> None:
    # Construct in mixed order and assert evaluation order via record.
    out: list[str] = []

    class _Tracker:
        name = "t"

        def __init__(self, p: int) -> None:
            self.priority = p

        async def evaluate(self, context: StopContext) -> StopSignalOutput:
            out.append(f"p{self.priority}")
            return StopSignalOutput(signal_name=self.name, result=SignalResult.DEFER)

    policy = StoppingPolicy(signals=[_Tracker(30), _Tracker(10), _Tracker(20)])
    await policy.evaluate(_state(sub_claims=[SubClaim(id="c1", text="t", status="pending")]))
    assert out == ["p10", "p20", "p30"]


async def test_policy_stops_at_first_stop_signal() -> None:
    """Later signals are not called once an earlier one returns STOP."""
    called: list[str] = []

    class _Stopper:
        name = "stop"
        priority = 1

        async def evaluate(self, context: StopContext) -> StopSignalOutput:
            called.append("stop")
            return StopSignalOutput(
                signal_name=self.name,
                result=SignalResult.STOP,
                stop_reason=StopReason.STOPPED_BY_BUDGET,
            )

    class _LaterShouldNotRun:
        name = "later"
        priority = 99

        async def evaluate(self, context: StopContext) -> StopSignalOutput:
            called.append("later")
            return StopSignalOutput(signal_name=self.name, result=SignalResult.DEFER)

    policy = StoppingPolicy(signals=[_Stopper(), _LaterShouldNotRun()])
    state = _state(sub_claims=[SubClaim(id="c1", text="t", status="pending")])
    result = await policy.evaluate(state)
    assert result.stop_reason is StopReason.STOPPED_BY_BUDGET
    assert called == ["stop"]


async def test_policy_log_keys_are_stable(caplog: pytest.LogCaptureFixture) -> None:
    """structlog events use stable keys (signal, result, stop_reason)."""
    # Render structlog to stdlib so caplog can see it.
    structlog.configure(
        processors=[
            structlog.processors.KeyValueRenderer(
                key_order=["signal", "result", "stop_reason"]
            ),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )
    state = _state(
        sub_claims=[SubClaim(id="c1", text="t", status="covered")],
        covered_claims=["c1"],
        search_count=20,
        max_searches=20,
    )
    state.evidence.append(_evidence())
    policy = StoppingPolicy(signals=[BudgetSignal()])

    with caplog.at_level(logging.DEBUG, logger="app.stopping.policy"):
        await policy.evaluate(state)

    rendered = " ".join(rec.getMessage() for rec in caplog.records)
    assert "signal=" in rendered
    assert "result=" in rendered
    structlog.reset_defaults()


def test_policy_default_signal_classes() -> None:
    """Default policy registers exactly the 5 spec'd signal types."""
    policy = StoppingPolicy()
    types = {type(s) for s in policy.signals}
    assert types == {
        AgreementSignal,
        BudgetSignal,
        CoverageSignal,
        HonestStopSignal,
        JudgeSignal,
    }


def test_stopping_signal_protocol_accepts_default_signals() -> None:
    for cls in (
        HonestStopSignal,
        BudgetSignal,
        CoverageSignal,
        AgreementSignal,
        JudgeSignal,
    ):
        assert isinstance(cls(), StoppingSignal)
