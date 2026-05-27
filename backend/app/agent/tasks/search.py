"""Search round execution.

One round = one call to :func:`execute_search_round`. Per pending claim
(capped at 5 per round) the cascade is Tavily → Wikipedia, falling
through on ``SourceError``.
"""

from __future__ import annotations

from uuid import uuid4

from app.agent.run_state import EvidenceItem, RunState
from app.domain.enums import EvidencePolarity, SourceType
from app.domain.events import (
    BaseEvent,
    EvidenceAddedEvent,
    SourceFailedEvent,
    ToolCalledEvent,
)
from app.seams.source import SourceError
from app.sources.registry import get_registry

_MAX_CLAIMS_PER_ROUND = 5
_RESULTS_PER_SEARCH = 3
_CASCADE_ORDER: list[SourceType] = [SourceType.TAVILY, SourceType.WIKIPEDIA]


async def execute_search_round(state: RunState) -> list[BaseEvent]:
    """Issue one cascading search per pending claim.

    Emits ``ToolCalled`` plus one of ``EvidenceAdded`` (success) or
    ``SourceFailed`` (recoverable failure, cascade continues).
    """
    registry = get_registry()
    available = registry.types()
    events: list[BaseEvent] = []

    for claim in state.pending_claims()[:_MAX_CLAIMS_PER_ROUND]:
        query = claim.text

        for source_type in _CASCADE_ORDER:
            if source_type not in available:
                continue

            events.append(
                ToolCalledEvent(
                    source_type=source_type,
                    query=query,
                    query_intent=f"Verify {claim.id}: {claim.text[:80]}",
                    target_claim_id=claim.id,
                )
            )

            try:
                results = await registry.get(source_type).search(
                    query, max_results=_RESULTS_PER_SEARCH
                )
            except SourceError as exc:
                events.append(
                    SourceFailedEvent(
                        source_type=source_type,
                        query=query,
                        error_message=exc.message,
                        recoverable=exc.recoverable,
                    )
                )
                state.failed_sources.append(f"{source_type.value}:{query}")
                continue

            for r in results:
                ev_id = uuid4()
                extracted = (r.snippet or "")[:1000]
                confidence = r.relevance_score if r.relevance_score is not None else 0.5
                ev = EvidenceAddedEvent(
                    id=ev_id,
                    source_type=source_type,
                    source_url=r.url,
                    source_title=r.title,
                    extracted_text=extracted,
                    polarity=EvidencePolarity.NEUTRAL,
                    target_claim_id=claim.id,
                    confidence=confidence,
                )
                events.append(ev)
                state.add_evidence(
                    EvidenceItem(
                        event_id=ev_id,
                        claim_id=claim.id,
                        source_url=r.url,
                        source_title=r.title,
                        text=extracted,
                        polarity=EvidencePolarity.NEUTRAL.value,
                        confidence=confidence,
                    )
                )
            break

    return events
