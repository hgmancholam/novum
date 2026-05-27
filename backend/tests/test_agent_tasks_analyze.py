"""Tests for ``app.agent.tasks.analyze``."""

from __future__ import annotations

from uuid import uuid4

from app.agent.run_state import EvidenceItem, RunState
from app.agent.tasks.analyze import analyze_evidence
from app.domain.events import (
    ClaimCoveredEvent,
    ClaimUncoverableEvent,
    SubClaim,
)


def _state() -> RunState:
    return RunState(
        run_id=uuid4(),
        question="Q?",
        sub_claims=[
            SubClaim(id="c1", text="t1", status="pending"),
            SubClaim(id="c2", text="t2", status="pending"),
        ],
    )


def _evidence(claim_id: str, conf: float) -> EvidenceItem:
    return EvidenceItem(
        claim_id=claim_id,
        source_url="https://example.com",
        source_title="ex",
        text="snippet",
        polarity="neutral",
        confidence=conf,
    )


async def test_two_evidence_above_threshold_covers_claim() -> None:
    state = _state()
    state.evidence = [_evidence("c1", 0.5), _evidence("c1", 0.5)]
    events = await analyze_evidence(state)
    covered = [e for e in events if isinstance(e, ClaimCoveredEvent)]
    assert len(covered) == 1
    assert covered[0].claim_id == "c1"
    assert "c1" in state.covered_claims
    assert len(covered[0].evidence_ids) == 2


async def test_one_evidence_no_coverage() -> None:
    state = _state()
    state.evidence = [_evidence("c1", 0.9)]
    events = await analyze_evidence(state)
    assert not any(isinstance(e, ClaimCoveredEvent) for e in events)


async def test_low_avg_confidence_does_not_cover() -> None:
    state = _state()
    state.evidence = [_evidence("c1", 0.1), _evidence("c1", 0.2)]
    events = await analyze_evidence(state)
    assert not any(isinstance(e, ClaimCoveredEvent) for e in events)


async def test_no_evidence_after_two_rounds_marks_uncoverable() -> None:
    state = _state()
    state.search_count = 2
    events = await analyze_evidence(state)
    uncoverable = [e for e in events if isinstance(e, ClaimUncoverableEvent)]
    assert len(uncoverable) == 2
    assert set(state.uncoverable_claims) == {"c1", "c2"}


async def test_no_evidence_before_two_rounds_keeps_pending() -> None:
    state = _state()
    state.search_count = 1
    events = await analyze_evidence(state)
    assert events == []
    assert state.uncoverable_claims == []
