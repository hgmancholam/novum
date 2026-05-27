"""Evidence analysis: claim coverage and uncoverability heuristic.

V1 placeholder rules. BRD-08 will replace this with the layered policy.
"""

from __future__ import annotations

from app.agent.run_state import RunState
from app.domain.events import (
    BaseEvent,
    ClaimCoveredEvent,
    ClaimUncoverableEvent,
)

COVERAGE_MIN_EVIDENCE = 2
COVERAGE_MIN_AVG_CONFIDENCE = 0.4
UNCOVERABLE_AFTER_ROUNDS = 2


async def analyze_evidence(state: RunState) -> list[BaseEvent]:
    """Mark pending claims as covered or uncoverable based on collected evidence."""
    events: list[BaseEvent] = []

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
