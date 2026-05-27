"""Tests for ``app.agent.run_state``."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.agent.run_state import EvidenceItem, RunState
from app.agent.states import AgentState
from app.domain.events import SubClaim


def _build_state(num_claims: int = 3) -> RunState:
    return RunState(
        run_id=uuid4(),
        question="What is X?",
        sub_claims=[
            SubClaim(id=f"c{i}", text=f"claim {i}", status="pending")
            for i in range(1, num_claims + 1)
        ],
    )


def test_transition_legal() -> None:
    state = _build_state()
    state.transition_to(AgentState.PLANNING)
    assert state.current_state == AgentState.PLANNING


def test_transition_illegal_raises() -> None:
    state = _build_state()
    with pytest.raises(ValueError, match="Invalid transition"):
        state.transition_to(AgentState.STOPPED) if False else None
        state.transition_to(AgentState.DRAFTING)


def test_transition_init_to_stopped_is_legal() -> None:
    state = _build_state()
    state.transition_to(AgentState.STOPPED)
    assert state.current_state == AgentState.STOPPED


def test_mark_claim_covered_flips_status_and_dedupes() -> None:
    state = _build_state()
    state.mark_claim_covered("c1")
    state.mark_claim_covered("c1")
    assert state.covered_claims == ["c1"]
    assert state.sub_claims[0].status == "covered"


def test_mark_claim_uncoverable_flips_status() -> None:
    state = _build_state()
    state.mark_claim_uncoverable("c2")
    assert state.uncoverable_claims == ["c2"]
    assert state.sub_claims[1].status == "uncoverable"


def test_pending_claims_filters_covered() -> None:
    state = _build_state()
    state.mark_claim_covered("c1")
    pending = state.pending_claims()
    assert {c.id for c in pending} == {"c2", "c3"}


def test_all_claims_resolved_false_when_pending() -> None:
    state = _build_state()
    assert state.all_claims_resolved() is False


def test_all_claims_resolved_true_when_all_resolved() -> None:
    state = _build_state()
    state.mark_claim_covered("c1")
    state.mark_claim_covered("c2")
    state.mark_claim_uncoverable("c3")
    assert state.all_claims_resolved() is True


def test_coverage_ratio_zero_when_no_claims() -> None:
    state = _build_state(num_claims=0)
    assert state.coverage_ratio() == 0.0


def test_coverage_ratio_partial() -> None:
    state = _build_state(num_claims=4)
    state.mark_claim_covered("c1")
    state.mark_claim_covered("c2")
    assert state.coverage_ratio() == 0.5


def test_coverage_ratio_full() -> None:
    state = _build_state(num_claims=2)
    state.mark_claim_covered("c1")
    state.mark_claim_covered("c2")
    assert state.coverage_ratio() == 1.0


def test_add_evidence_appends() -> None:
    state = _build_state()
    ev = EvidenceItem(
        claim_id="c1",
        source_url="https://example.com",
        source_title="ex",
        text="snippet",
        polarity="neutral",
        confidence=0.5,
    )
    state.add_evidence(ev)
    assert state.evidence == [ev]


def test_json_round_trip() -> None:
    state = _build_state()
    state.mark_claim_covered("c1")
    payload = state.model_dump_json()
    reloaded = RunState.model_validate_json(payload)
    assert reloaded.covered_claims == ["c1"]
    assert reloaded.sub_claims[0].status == "covered"


def test_run_state_has_ambiguity_default_false() -> None:
    state = _build_state()
    assert state.has_ambiguity is False

