"""Evidence analysis: claim coverage, uncoverability, and contradiction detection.

V1 placeholder rules for coverage. WP-2.5 adds contradiction detection:
- Each evidence chunk has a stance (supports/contradicts/neutral)
- ContradictionDetectedEvent emitted when same claim has ≥1 supports AND ≥1 contradicts
- Evaluated cumulatively across rounds
"""

from __future__ import annotations

from collections import defaultdict
from typing import Literal

from app.agent.run_state import RunState
from app.domain.events import (
    BaseEvent,
    ClaimCoveredEvent,
    ClaimUncoverableEvent,
    ContradictionDetectedEvent,
)

COVERAGE_MIN_EVIDENCE = 2
COVERAGE_MIN_AVG_CONFIDENCE = 0.4
UNCOVERABLE_AFTER_ROUNDS = 2

# WP-2.5: stance mapping
EvidenceStance = Literal["supports", "contradicts", "neutral"]


def _map_polarity_to_stance(polarity: str) -> EvidenceStance:
    """Map EvidenceItem.polarity to stance for contradiction detection.

    WP-2.5: the polarity field is set by the search handler. We interpret:
    - "supports" → supports
    - "contradicts" / "opposes" / "refutes" → contradicts
    - anything else → neutral
    """
    polarity_lower = polarity.lower()
    if polarity_lower == "supports":
        return "supports"
    elif polarity_lower in {"contradicts", "opposes", "refutes"}:
        return "contradicts"
    else:
        return "neutral"


async def analyze_evidence(state: RunState) -> list[BaseEvent]:
    """Mark pending claims as covered or uncoverable; detect contradictions.

    WP-2.5 addition: emit ContradictionDetectedEvent when the same claim has
    evidence with opposite stances (≥1 supports AND ≥1 contradicts).
    """
    events: list[BaseEvent] = []

    # Group evidence by claim for contradiction detection
    claim_stances: dict[str, dict[EvidenceStance, list]] = defaultdict(
        lambda: {"supports": [], "contradicts": [], "neutral": []}
    )

    for evidence_item in state.evidence:
        stance = _map_polarity_to_stance(evidence_item.polarity)
        claim_stances[evidence_item.claim_id][stance].append(evidence_item)

    # Check for contradictions (cumulative across rounds)
    for claim in state.sub_claims:
        stances = claim_stances.get(claim.id)
        if not stances:
            continue

        has_supports = len(stances["supports"]) > 0
        has_contradicts = len(stances["contradicts"]) > 0

        if has_supports and has_contradicts:
            # Emit ContradictionDetectedEvent with WP-2.5 payload
            supporting_chunk_ids = [str(e.event_id) for e in stances["supports"]]
            contradicting_chunk_ids = [str(e.event_id) for e in stances["contradicts"]]

            # Pick one example from each side for the legacy payload
            example_support = stances["supports"][0]
            example_contradict = stances["contradicts"][0]

            event = ContradictionDetectedEvent(
                claim_id=claim.id,
                source_a={
                    "url": example_support.source_url,
                    "title": example_support.source_title,
                    "claim": example_support.text[:200],
                },
                source_b={
                    "url": example_contradict.source_url,
                    "title": example_contradict.source_title,
                    "claim": example_contradict.text[:200],
                },
                nature_of_conflict=(
                    f"{len(supporting_chunk_ids)} sources support, "
                    f"{len(contradicting_chunk_ids)} sources contradict"
                ),
            )
            # WP-2.5 new optional fields
            event.claim = claim.text
            event.supporting_chunk_ids = supporting_chunk_ids
            event.contradicting_chunk_ids = contradicting_chunk_ids
            event.round = state.search_count

            events.append(event)

    # Original coverage logic
    for claim in list(state.pending_claims()):
        claim_evidence = [e for e in state.evidence if e.claim_id == claim.id]

        if len(claim_evidence) >= COVERAGE_MIN_EVIDENCE:
            avg_conf = sum(e.confidence for e in claim_evidence) / len(claim_evidence)
            if avg_conf >= COVERAGE_MIN_AVG_CONFIDENCE:
                state.mark_claim_covered(claim.id)
                events.append(
                    ClaimCoveredEvent(
                        claim_id=claim.id,
                        claim_text=claim.text,
                        evidence_ids=[e.event_id for e in claim_evidence],
                        coverage_rationale=(
                            f"{len(claim_evidence)} sources, avg confidence {avg_conf:.2f}"
                        ),
                    )
                )
                continue

        if not claim_evidence and state.search_count >= UNCOVERABLE_AFTER_ROUNDS:
            state.mark_claim_uncoverable(claim.id)
            events.append(
                ClaimUncoverableEvent(
                    claim_id=claim.id,
                    claim_text=claim.text,
                    reason="No relevant evidence found after 2 search rounds",
                    attempted_sources=[],
                )
            )

    return events
