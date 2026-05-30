"""Stuck-planner signal — repeated top-URL detector (Post-PR-7).

Fires when the last two reformulation generations return roughly the
same set of source URLs (Jaccard overlap >= threshold). This catches
the failure mode where the planner keeps reformulating queries but the
underlying source backends keep returning the same top-N results, so
no new evidence is actually being discovered.

Independent of ``no_progress`` (which looks at *coverage*) and
``budget`` (which counts reformulations): a planner can be stuck at
high coverage with a tiny URL pool, or stuck below the reformulation
cap with a wide pool. Only this signal catches "same URLs, different
queries".
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.config import settings

if TYPE_CHECKING:
    from app.agent.run_state import RunState

logger = structlog.get_logger(__name__)


def check_stuck_planner(state: RunState) -> bool:
    """Fire when the last two reformulation generations share >= ``min_overlap`` URLs.

    A "generation" is the set of unique ``source_url`` values from
    ``EvidenceAdded`` events emitted between two consecutive
    ``QueryReformulated`` events (or between run start and the first
    reformulation). Generations smaller than ``min_urls_per_gen`` are
    ignored to avoid spurious matches on near-empty rounds.

    Returns True when both:
      * ``stuck_planner_enabled`` is True (kill switch).
      * At least two non-trivial generations exist.
      * Jaccard(last, prev) >= ``stuck_planner_min_overlap``.
    """
    if not settings.stuck_planner_enabled:
        return False

    generations: list[set[str]] = []
    current: set[str] = set()
    for ev in state.events:
        type_value = getattr(ev.type, "value", str(ev.type))
        if type_value == "QueryReformulated":
            if current:
                generations.append(current)
                current = set()
        elif type_value == "EvidenceAdded":
            url = getattr(ev, "source_url", None)
            if isinstance(url, str) and url:
                current.add(url)
    if current:
        generations.append(current)

    min_urls = settings.stuck_planner_min_urls_per_gen
    non_trivial = [g for g in generations if len(g) >= min_urls]
    if len(non_trivial) < 2:
        return False

    prev = non_trivial[-2]
    last = non_trivial[-1]
    union = prev | last
    if not union:
        return False
    overlap = len(prev & last) / len(union)
    if overlap >= settings.stuck_planner_min_overlap:
        logger.warning(
            "stuck_planner_detected",
            overlap=round(overlap, 3),
            prev_urls=len(prev),
            last_urls=len(last),
            generations_total=len(non_trivial),
        )
        return True
    return False
