"""Instant answer cache for question normalization and LRU storage.

BRD-22 Phase 6: In-memory cache (cleared on uvicorn restart) keyed by
(username, normalised_question). LRU eviction via OrderedDict when size
exceeds settings.instant_cache_max_size.
"""

import unicodedata
from collections import OrderedDict
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.config import settings
from app.domain.enums import AnswerKind, StopReason
from app.domain.events import Citation


def normalise_question(s: str) -> str:
    """Normalise question string for cache key matching.

    Lowercases, strips Unicode punctuation (via unicodedata.category),
    collapses whitespace, and strips leading/trailing whitespace.

    Args:
        s: Raw question string.

    Returns:
        Normalised string suitable for cache key comparison.
    """
    # Strip Unicode punctuation characters
    chars = [c for c in s if not unicodedata.category(c).startswith("P")]
    cleaned = "".join(chars)
    # Lowercase and collapse whitespace
    cleaned = cleaned.lower()
    # Collapse multiple whitespace into single space
    cleaned = " ".join(cleaned.split())
    return cleaned.strip()


class CachedRun(BaseModel):
    """Payload stored in instant cache for a high-confidence terminal run.

    Mirrors the fields of StoppedEvent / RunState that are needed to
    replay an answer without re-running the research pipeline.
    """

    model_config = ConfigDict(extra="allow")

    run_id: UUID
    final_confidence: float
    judge_confidence: float | None
    structural_confidence: float | None
    stop_reason: StopReason
    answer_kind: AnswerKind | None
    answer_prose: str | None
    answer_structured: str | None
    answer_structured_data: dict[str, Any] | None
    citations: list[Citation] | None
    completed_at: datetime


# Module-level LRU cache: (username, normalised_question) -> CachedRun
_cache: OrderedDict[tuple[str, str], CachedRun] = OrderedDict()


def record_run(username: str, question: str, payload: CachedRun) -> None:
    """Record a terminal high-confidence run in the instant cache.

    Called by orchestrator when a run terminates with StopReason.JUDGE_CONFIRMED
    and judge_confidence is not None. Uses LRU eviction when size exceeds
    settings.instant_cache_max_size.

    Args:
        username: Owner username (cache key component).
        question: Raw question string (will be normalised).
        payload: Cached answer data.
    """
    norm_q = normalise_question(question)
    key = (username, norm_q)

    # LRU: move to end (most recent)
    if key in _cache:
        _cache.move_to_end(key)
    _cache[key] = payload

    # Evict oldest if over capacity
    while len(_cache) > settings.instant_cache_max_size:
        _cache.popitem(last=False)


def try_replay(username: str, question: str) -> CachedRun | None:
    """Attempt to retrieve a cached answer for the given (user, question).

    Returns None if:
    - Cache miss
    - final_confidence < settings.instant_cache_min_confidence
    - stop_reason != StopReason.JUDGE_CONFIRMED
    - Either username or question is falsy

    Args:
        username: Owner username.
        question: Raw question string (will be normalised).

    Returns:
        CachedRun if replay is valid, else None.
    """
    if not username or not question:
        return None

    norm_q = normalise_question(question)
    key = (username, norm_q)

    cached = _cache.get(key)
    if cached is None:
        return None

    # LRU: move to end on hit
    _cache.move_to_end(key)

    # Validate confidence and stop_reason thresholds
    if cached.final_confidence < settings.instant_cache_min_confidence:
        return None
    if cached.stop_reason != StopReason.JUDGE_CONFIRMED:
        return None

    return cached


def reset_instant_cache() -> None:
    """Clear all cached runs. Used by tests and shutdown hooks."""
    _cache.clear()
