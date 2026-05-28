"""Deep-fetch escalation task (BRD-23 WP-2).

When the judge flags a claim as ``supported_but_shallow`` (snippet was
insufficient or all citations were stale), we synchronously call
``Source.fetch_full`` on the most relevant supporting evidence URL,
emit a ``DeepFetchPerformedEvent`` (success or failure), update the
in-memory ``EvidenceItem.text`` on success, and let the orchestrator
re-route back to ANALYZING for a fresh judge pass.

Budget is enforced per-run via complexity_hint: trivial=0, standard=2,
deep=3. The counter is recomputed from the event log on every call to
avoid adding a dedicated ``RunState`` counter (L-015).
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

import structlog

from app.agent.run_state import EvidenceItem, RunState
from app.config import settings
from app.domain.enums import ComplexityHint, EventType, SourceType
from app.domain.events import DeepFetchPerformedEvent

if TYPE_CHECKING:
    from app.sources.registry import SourceRegistry

logger = structlog.get_logger(__name__)


type EmitCallback = Callable[[DeepFetchPerformedEvent], Awaitable[None]]


def _deep_fetch_budget(complexity_hint: ComplexityHint | None) -> int:
    """Per-run cap on deep-fetch calls (BRD-23 §4.6 budget table)."""
    if complexity_hint is ComplexityHint.TRIVIAL:
        return settings.deep_fetch_max_per_run_trivial
    if complexity_hint is ComplexityHint.DEEP:
        return settings.deep_fetch_max_per_run_deep
    # STANDARD or None default to STANDARD.
    return settings.deep_fetch_max_per_run_standard


def _count_deep_fetches(state: RunState) -> int:
    """Recompute the deep-fetch counter from the event log.

    Per L-015 we do not add a typed ``RunState`` field. Live runs do not
    populate ``state.events`` (the emit callback writes straight to the
    DB), so we keep a transient counter in ``state.metadata`` keyed under
    ``deep_fetch_count_live`` and take the max with whatever the
    resume-folded ``state.events`` reports. After resume, both numbers
    agree.
    """
    folded = sum(
        1 for ev in state.events if ev.type == EventType.DEEP_FETCH_PERFORMED
    )
    live = int(state.metadata.get("deep_fetch_count_live", 0))
    return max(folded, live)


def _is_short(text: str | None) -> bool:
    if text is None:
        return True
    return len(text) < settings.deep_fetch_min_snippet_chars


def _candidate_evidence(
    state: RunState, claim_id: str
) -> EvidenceItem | None:
    """Pick the highest-confidence supporting evidence row for ``claim_id``.

    Skips rows whose text already exceeds the snippet threshold (no
    point re-fetching). Returns ``None`` if no candidate is suitable.
    """
    supporting = [
        ev
        for ev in state.evidence
        if ev.claim_id == claim_id and ev.polarity == "supports" and _is_short(ev.text)
    ]
    if not supporting:
        return None
    supporting.sort(key=lambda ev: ev.confidence, reverse=True)
    return supporting[0]


async def maybe_deep_fetch(
    state: RunState,
    shallow_claim_ids: list[str] | None,
    *,
    registry: SourceRegistry,
    emit: EmitCallback,
) -> bool:
    """Run the WP-2 deep-fetch escalation pass.

    Returns ``True`` if at least one deep fetch succeeded and the
    orchestrator should loop back to ANALYZING; ``False`` otherwise.

    Caller (orchestrator) is responsible for the cancellation check
    immediately before and after the call.
    """
    shallow_ids = shallow_claim_ids or []
    if not shallow_ids:
        return False

    budget = _deep_fetch_budget(state.complexity_hint)
    used = _count_deep_fetches(state)
    remaining = max(0, budget - used)
    if remaining == 0:
        logger.info(
            "deep_fetch_budget_exhausted",
            run_id=str(state.run_id),
            budget=budget,
            used=used,
        )
        return False

    targets = shallow_ids[: min(remaining, settings.deep_fetch_top_k)]
    any_success = False
    for claim_id in targets:
        evidence = _candidate_evidence(state, claim_id)
        if evidence is None:
            continue
        source_type = _infer_source_type(evidence.source_url)
        try:
            source = registry.get(source_type)
        except ValueError:
            logger.warning(
                "deep_fetch_no_source", url=evidence.source_url, source_type=source_type.value
            )
            continue

        started = time.monotonic()
        success = False
        failure_reason: str | None = None
        content_length = 0
        try:
            result = await source.fetch_full(
                evidence.source_url, timeout=settings.deep_fetch_timeout_s
            )
        except Exception as exc:
            result = None
            failure_reason = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "deep_fetch_exception",
                url=evidence.source_url,
                error=failure_reason,
            )
        fetch_ms = int((time.monotonic() - started) * 1000)

        if result is not None and result.content:
            evidence.text = result.content
            content_length = len(result.content)
            success = True
            any_success = True
        elif failure_reason is None:
            failure_reason = "empty_or_unavailable"

        await emit(
            DeepFetchPerformedEvent(
                source_type=source_type,
                url=evidence.source_url,
                triggered_by_claim_id=claim_id,
                fetch_ms=fetch_ms,
                content_length=content_length,
                success=success,
                failure_reason=failure_reason if not success else None,
            )
        )
        state.metadata["deep_fetch_count_live"] = (
            int(state.metadata.get("deep_fetch_count_live", 0)) + 1
        )

    return any_success


def _infer_source_type(url: str) -> SourceType:
    """Best-effort source-type inference from a URL."""
    if "wikipedia.org" in url.lower():
        return SourceType.WIKIPEDIA
    return SourceType.TAVILY
