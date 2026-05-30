"""Search round execution.

One round = one call to :func:`execute_search_round`. Per pending claim
(capped at 5 per round) the cascade is Tavily → Wikipedia, falling
through on ``SourceError``.

IP-25 Phase 0: Per-claim searches run in parallel via asyncio.gather.
Query reformulation triggered when all Tavily results have relevance_score < 0.3.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.agent.run_state import EvidenceItem, RunState
from app.agent.source_hints import build_source_hints
from app.agent.sources_authority import match as match_authority_tier
from app.domain.enums import EvidencePolarity, SourceType, TemporalSensitivity
from app.domain.events import (
    BaseEvent,
    EvidenceAddedEvent,
    QueryReformulatedEvent,
    SourceFailedEvent,
    SubClaim,
    ToolCalledEvent,
)
from app.seams.source import SourceError
from app.sources.registry import get_registry

_MAX_CLAIMS_PER_ROUND = 5
_RESULTS_PER_SEARCH = 3
_CASCADE_ORDER: list[SourceType] = [SourceType.TAVILY, SourceType.WIKIPEDIA]
_MIN_RELEVANCE_THRESHOLD = 0.3

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


async def _search_one_claim(
    claim: SubClaim,
    cascade: list[SourceType],
    days_filter: int | None,
    state: RunState,
) -> list[BaseEvent]:
    """Execute cascading search for a single claim without mutating state.

    Returns a list of events (ToolCalled, EvidenceAdded, SourceFailed,
    QueryReformulated) in the order they were generated. The caller is
    responsible for applying state mutations.

    IP-25 Phase 0: Implements low-relevance query reformulation. If ALL
    Tavily results have relevance_score < 0.3, performs ONE reformulated
    retry with query = "{claim.text} {question[:40]}".
    """
    registry = get_registry()
    available = registry.types()
    events: list[BaseEvent] = []
    query = claim.text
    reformulated = False

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

        hints = build_source_hints(state)
        try:
            source = registry.get(source_type)
            if source_type == SourceType.TAVILY and tool_days is not None:
                results = await source.search(
                    query,
                    max_results=_RESULTS_PER_SEARCH,
                    days=tool_days,
                    **hints,
                )
            else:
                results = await source.search(
                    query, max_results=_RESULTS_PER_SEARCH, **hints
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
            continue

        # IP-25 Phase 0: Check for low-relevance trigger on Tavily
        if (
            source_type == SourceType.TAVILY
            and not reformulated
            and results
            and all(
                (r.relevance_score or 0.0) < _MIN_RELEVANCE_THRESHOLD for r in results
            )
        ):
            # Emit reformulation event and retry ONCE
            reformulated_query = f"{claim.text} {state.question[:40]}"
            events.append(
                QueryReformulatedEvent(
                    original_query=query,
                    reformulated_query=reformulated_query,
                    target_claim_id=claim.id,
                    reason="low_relevance",
                )
            )
            query = reformulated_query
            reformulated = True

            # Retry with reformulated query
            events.append(
                ToolCalledEvent(
                    source_type=source_type,
                    query=query,
                    query_intent=f"Verify (reformulated) {claim.id}: {claim.text[:80]}",
                    target_claim_id=claim.id,
                    query_length_tokens=_count_query_tokens(query),
                    tavily_days_filter=tool_days,
                )
            )

            try:
                if tool_days is not None:
                    results = await source.search(
                        query,
                        max_results=_RESULTS_PER_SEARCH,
                        days=tool_days,
                        **hints,
                    )
                else:
                    results = await source.search(
                        query, max_results=_RESULTS_PER_SEARCH, **hints
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
                continue

        # Process results and create EvidenceAdded events
        for r in results:
            ev_id = uuid4()
            extracted = (r.snippet or "")[:1000]
            confidence = r.relevance_score if r.relevance_score is not None else 0.5
            published = _parse_published_date(getattr(r, "published_date", None))
            authority_tier = match_authority_tier(r.url)
            events.append(
                EvidenceAddedEvent(
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
            )
        if results:
            # Success: break cascade. Empty results (200 OK with data:[])
            # falls through to the next source so academic-first questions
            # don't dead-end on Semantic Scholar.
            break

    return events


async def execute_search_round(state: RunState) -> list[BaseEvent]:
    """Issue one cascading search per pending claim in parallel.

    IP-25 Phase 0: Per-claim searches run concurrently via asyncio.gather.
    State mutations (add_evidence, failed_sources) are applied sequentially
    after all searches complete to preserve deterministic replay.

    Emits ``ToolCalled`` plus one of ``EvidenceAdded`` (success) or
    ``SourceFailed`` (recoverable failure, cascade continues). May also
    emit ``QueryReformulated`` when low-relevance triggers reformulation.
    """
    # BRD-23 WP-1: pre-compute days filter based on temporal sensitivity
    temporal = state.temporal_sensitivity
    days_filter = _TAVILY_DAYS_BY_TEMPORAL.get(temporal) if temporal is not None else None

    # Cascade: planner-preferred sources first (academic questions add
    # semantic_scholar / openalex), then the defaults as last-resort
    # fallback so every claim still has Wikipedia to fall back to.
    cascade: list[SourceType] = []
    for raw in state.preferred_sources:
        try:
            st = SourceType(raw)
        except ValueError:
            continue
        if st not in cascade:
            cascade.append(st)
    for st in _CASCADE_ORDER:
        if st not in cascade:
            cascade.append(st)

    # BRD-23 WP-1: realtime topics skip Wikipedia entirely
    if temporal == TemporalSensitivity.REALTIME:
        cascade = [s for s in cascade if s != SourceType.WIKIPEDIA]

    # IP-30: skip academic sources for domains that consistently return [].
    # Geopolitics / lifestyle / history questions are answered by news,
    # institutional reports, or general references rather than peer-reviewed
    # journals; calling S2/OpenAlex wastes a round-trip per claim. Domain
    # is OPTIONAL on RunState so legacy replays (None) keep both sources.
    if state.domain is not None and state.domain.value in {
        "geopolitics", "lifestyle", "history"
    }:
        cascade = [
            s for s in cascade
            if s not in (SourceType.SEMANTIC_SCHOLAR, SourceType.OPENALEX)
        ]

    # IP-25 Phase 0: Run per-claim searches in parallel
    claims = state.pending_claims()[:_MAX_CLAIMS_PER_ROUND]
    per_claim_events = await asyncio.gather(
        *[_search_one_claim(claim, cascade, days_filter, state) for claim in claims]
    )

    # Flatten events and apply state mutations in deterministic order
    all_events: list[BaseEvent] = []
    for events_for_claim in per_claim_events:
        for event in events_for_claim:
            all_events.append(event)
            # Apply state mutations for EvidenceAdded and SourceFailed
            if isinstance(event, EvidenceAddedEvent):
                state.add_evidence(
                    EvidenceItem(
                        event_id=event.id or uuid4(),
                        claim_id=event.target_claim_id,
                        source_url=event.source_url,
                        source_title=event.source_title,
                        text=event.extracted_text,
                        polarity=event.polarity.value,
                        confidence=event.confidence,
                        source_published_date=event.source_published_date,
                        authority_tier=event.authority_tier,
                    )
                )
            elif isinstance(event, SourceFailedEvent):
                state.failed_sources.append(f"{event.source_type.value}:{event.query}")

    return all_events
