"""Tests for WP-2.5 contradiction detector contract.

Verifies:
- Opposite stances (supports + contradicts) trigger ContradictionDetectedEvent
- Same stances (all supports) do NOT trigger
- Cross-round cumulative detection works
- New payload fields (claim, supporting_chunk_ids, contradicting_chunk_ids, round) are populated
"""

from uuid import uuid4

import pytest

from app.agent.run_state import EvidenceItem, RunState
from app.agent.tasks.analyze import analyze_evidence
from app.domain.events import ContradictionDetectedEvent, SubClaim


@pytest.fixture
def base_state() -> RunState:
    """Minimal RunState for analyzer tests."""
    state = RunState(
        run_id=uuid4(),
        question="Test question",
    )
    state.sub_claims = [
        SubClaim(id="c1", text="Claim 1", status="pending"),
    ]
    return state


@pytest.mark.asyncio
async def test_opposite_stances_emit_contradiction(base_state: RunState) -> None:
    """Two chunks with opposite stances (supports + contradicts) emit event."""
    base_state.evidence = [
        EvidenceItem(
            claim_id="c1",
            source_url="https://example.com/a",
            source_title="Source A",
            text="Evidence supports the claim",
            polarity="supports",
            confidence=0.9,
        ),
        EvidenceItem(
            claim_id="c1",
            source_url="https://example.com/b",
            source_title="Source B",
            text="Evidence contradicts the claim",
            polarity="contradicts",
            confidence=0.9,
        ),
    ]
    base_state.search_count = 1

    events = await analyze_evidence(base_state)

    contradiction_events = [e for e in events if isinstance(e, ContradictionDetectedEvent)]
    assert len(contradiction_events) == 1

    event = contradiction_events[0]
    assert event.claim_id == "c1"
    assert event.claim == "Claim 1"
    assert event.supporting_chunk_ids is not None
    assert len(event.supporting_chunk_ids) == 1
    assert event.contradicting_chunk_ids is not None
    assert len(event.contradicting_chunk_ids) == 1
    assert event.round == 1


@pytest.mark.asyncio
async def test_same_stance_no_contradiction(base_state: RunState) -> None:
    """Two chunks with same stance (both supports) do NOT emit event."""
    base_state.evidence = [
        EvidenceItem(
            claim_id="c1",
            source_url="https://example.com/a",
            source_title="Source A",
            text="Evidence supports",
            polarity="supports",
            confidence=0.9,
        ),
        EvidenceItem(
            claim_id="c1",
            source_url="https://example.com/b",
            source_title="Source B",
            text="More support",
            polarity="supports",
            confidence=0.9,
        ),
    ]
    base_state.search_count = 1

    events = await analyze_evidence(base_state)

    contradiction_events = [e for e in events if isinstance(e, ContradictionDetectedEvent)]
    assert len(contradiction_events) == 0


@pytest.mark.asyncio
async def test_cross_round_cumulative_detection(base_state: RunState) -> None:
    """Supports in round 1 + contradicts in round 2 → event fires in round 2."""
    # Round 1: only supports
    base_state.evidence = [
        EvidenceItem(
            claim_id="c1",
            source_url="https://example.com/a",
            source_title="Source A",
            text="Supports",
            polarity="supports",
            confidence=0.9,
        ),
    ]
    base_state.search_count = 1

    events_round1 = await analyze_evidence(base_state)
    contradiction_events_round1 = [
        e for e in events_round1 if isinstance(e, ContradictionDetectedEvent)
    ]
    assert len(contradiction_events_round1) == 0

    # Round 2: add contradicting evidence
    base_state.evidence.append(
        EvidenceItem(
            claim_id="c1",
            source_url="https://example.com/b",
            source_title="Source B",
            text="Contradicts",
            polarity="contradicts",
            confidence=0.9,
        )
    )
    base_state.search_count = 2

    events_round2 = await analyze_evidence(base_state)
    contradiction_events_round2 = [
        e for e in events_round2 if isinstance(e, ContradictionDetectedEvent)
    ]
    assert len(contradiction_events_round2) == 1

    event = contradiction_events_round2[0]
    assert event.round == 2
    assert len(event.supporting_chunk_ids) == 1
    assert len(event.contradicting_chunk_ids) == 1


@pytest.mark.asyncio
async def test_neutral_stance_does_not_trigger(base_state: RunState) -> None:
    """Neutral stance does not count toward contradiction detection."""
    base_state.evidence = [
        EvidenceItem(
            claim_id="c1",
            source_url="https://example.com/a",
            source_title="Source A",
            text="Supports",
            polarity="supports",
            confidence=0.9,
        ),
        EvidenceItem(
            claim_id="c1",
            source_url="https://example.com/b",
            source_title="Source B",
            text="Neutral mention",
            polarity="neutral",
            confidence=0.5,
        ),
    ]
    base_state.search_count = 1

    events = await analyze_evidence(base_state)

    contradiction_events = [e for e in events if isinstance(e, ContradictionDetectedEvent)]
    assert len(contradiction_events) == 0
