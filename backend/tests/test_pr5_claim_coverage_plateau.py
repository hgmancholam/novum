"""PR-5 unit tests — claim-coverage plateau predicate.

Verifies the new event-independent no-progress detector that fires when three
consecutive analyze rounds add zero new covered claims (Q2/Q6 stall mode from
the 29/05 batch).
"""

from __future__ import annotations

from uuid import uuid4

from app.agent.run_state import RunState
from app.stopping.signals.no_progress import check_claim_coverage_plateau


def _make_state() -> RunState:
    return RunState(
        run_id=uuid4(),
        question="q",
        owner_username="tester",
    )


def test_coverage_plateau_warmup_does_not_fire() -> None:
    """Fewer than 4 snapshots (3 rounds delta) → never fire."""
    state = _make_state()
    state.coverage_history = []
    assert check_claim_coverage_plateau(state) is False
    state.coverage_history = [0, 0, 0]
    assert check_claim_coverage_plateau(state) is False


def test_coverage_plateau_fires_when_3_consecutive_rounds_no_growth() -> None:
    """4 snapshots with identical last and -4 entry → fire."""
    state = _make_state()
    state.coverage_history = [2, 2, 2, 2]
    assert check_claim_coverage_plateau(state) is True


def test_coverage_plateau_does_not_fire_with_growth() -> None:
    """Any growth within the last 3 round delta → do not fire."""
    state = _make_state()
    # 3 rounds back was 1, now 3 → grew
    state.coverage_history = [1, 2, 2, 3]
    assert check_claim_coverage_plateau(state) is False
    # Single bump at the end is enough
    state.coverage_history = [4, 4, 4, 5]
    assert check_claim_coverage_plateau(state) is False


def test_coverage_plateau_custom_rounds() -> None:
    """``rounds`` arg controls the window; rounds=2 needs 3 snapshots."""
    state = _make_state()
    state.coverage_history = [5, 5, 5]
    assert check_claim_coverage_plateau(state, rounds=2) is True
    state.coverage_history = [5, 5]  # warm-up for rounds=2
    assert check_claim_coverage_plateau(state, rounds=2) is False


def test_coverage_plateau_late_growth_recovers() -> None:
    """Plateau across rounds 1-4 but late growth on round 5 → do not fire."""
    state = _make_state()
    state.coverage_history = [2, 2, 2, 2, 4]  # last vs last-4 differs
    assert check_claim_coverage_plateau(state) is False
