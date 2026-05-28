"""Search round execution.

One round = one call to :func:`execute_search_round`. Per pending claim
(capped at 5 per round) the cascade is Tavily → Wikipedia, falling
through on ``SourceError``.
"""

from __future__ import annotations

from uuid import uuid4

from datetime import datetime

from app.agent.run_state import EvidenceItem, RunState
from app.agent.sources_authority import match as match_authority_tier
from app.domain.enums import EvidencePolarity, SourceType, TemporalSensitivity
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

# BRD-23 WP-1: temporal_sensitivity → Tavily ``days`` filter
_TAVILY_DAYS_BY_TEMPORAL: dict[TemporalSensitivity, int | None] = {
    TemporalSensitivity.STATIC: None,
    TemporalSensitivity.SLOW_CHANGING: 730,
    TemporalSensitivity.VOLATILE: 180,
    TemporalSensitivity.REALTIME: 7,
}


def _count_query_tokens(query: str) -> int:
    """Whitespace-split token count for ``ToolCalledEvent.query_length_tokens`` (BRD-23 WP-4)."""
    return len(query.split())


def _parse_published_date(raw: str | None) -> datetime | None:
    """Best-effort parse of Tavily ``published_date`` strings (BRD-23 WP-1)."""
    if not raw:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


async def execute_search_round(state: RunState) -> list[BaseEvent]:
    """Issue one cascading search per pending claim.

    Emits ``ToolCalled`` plus one of ``EvidenceAdded`` (success) or
    ``SourceFailed`` (recoverable failure, cascade continues).
    """
    registry = get_registry()
    available = registry.types()
    events: list[BaseEvent] = []

    # BRD-23 WP-1: pre-compute days filter based on temporal sensitivity
    temporal = state.temporal_sensitivity
    days_filter = _TAVILY_DAYS_BY_TEMPORAL.get(temporal) if temporal is not None else None

    # BRD-23 WP-1: realtime topics skip Wikipedia entirely
    cascade = list(_CASCADE_ORDER)
    if temporal == TemporalSensitivity.REALTIME:
        cascade = [s for s in cascade if s != SourceType.WIKIPEDIA]

    for claim in state.pending_claims()[:_MAX_CLAIMS_PER_ROUND]:
        query = claim.text

        for source_type in cascade:
            if source_type not in available:
                continue

            tool_days = days_filter if source_type == SourceType.TAVILY else None
            events.append(
                ToolCalledEvent(
                    source_type=source_type,
                    query=query,
                    query_intent=f"Verify {claim.id}: {claim.text[:80]}",
                    target_claim_id=claim.id,
                    query_length_tokens=_count_query_tokens(query),
                    tavily_days_filter=tool_days,
                )
            )

            try:
                source = registry.get(source_type)
                if source_type == SourceType.TAVILY and tool_days is not None:
                    results = await source.search(
                        query, max_results=_RESULTS_PER_SEARCH, days=tool_days
                    )
                else:
                    results = await source.search(
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
                published = _parse_published_date(getattr(r, "published_date", None))
                authority_tier = match_authority_tier(r.url)
                ev = EvidenceAddedEvent(
                    id=ev_id,
                    source_type=source_type,
                    source_url=r.url,
                    source_title=r.title,
                    extracted_text=extracted,
                    polarity=EvidencePolarity.NEUTRAL,
                    target_claim_id=claim.id,
                    confidence=confidence,
                    source_published_date=published,
                    authority_tier=authority_tier,
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
                        source_published_date=published,
                        authority_tier=authority_tier,
                    )
                )
            break

    return events
