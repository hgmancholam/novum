"""In-process exact-match cache for CLASSIFIER LLM calls (Post-PR-8).

Why only CLASSIFIER:
  * Output is a discriminated enum (``QuestionClassification``) — same
    input deterministically yields the same classification.
  * It is the cheapest role to call, but it runs on every single run
    (lane router, plus replans). Caching it is pure latency + token win
    with no calibration risk.

Why NOT planner / synthesizer / judge:
  * Their value is the variability across runs (different evidence,
    different drafts). Caching them would turn the agent into a glorified
    FAQ and break Plan-B / live re-evaluation.

The cache is a bounded LRU with a per-entry TTL. Eviction policy is
"max-entries" first, "expired" lazy on lookup. Process-local — when the
server restarts the cache empties (acceptable in V1 single-server).
"""

from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from typing import Any

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

_CACHE: OrderedDict[str, tuple[float, Any]] = OrderedDict()
_HITS = 0
_MISSES = 0


def _key(model: str, messages: list[dict[str, Any]], response_model_name: str) -> str:
    """Stable hash of the request that fully determines the classifier output."""
    parts: list[str] = [model, response_model_name]
    for m in messages:
        role = str(m.get("role", ""))
        content = m.get("content", "")
        # cache_control wrapping (Anthropic) puts content in a list — flatten
        # to its text so the same logical prompt with or without caching
        # hashes identically.
        if isinstance(content, list):
            content = "".join(
                str(block.get("text", "")) for block in content
                if isinstance(block, dict)
            )
        parts.append(f"{role}:{content}")
    raw = "\u241f".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def get(model: str, messages: list[dict[str, Any]], response_model_name: str) -> Any | None:
    """Return cached response or ``None``. Pure read; updates LRU recency."""
    global _HITS, _MISSES
    if not settings.classifier_cache_enabled:
        return None
    k = _key(model, messages, response_model_name)
    entry = _CACHE.get(k)
    if entry is None:
        _MISSES += 1
        return None
    expires_at, value = entry
    if time.time() >= expires_at:
        _CACHE.pop(k, None)
        _MISSES += 1
        return None
    _CACHE.move_to_end(k)
    _HITS += 1
    logger.info("classifier_cache_hit", hits=_HITS, misses=_MISSES)
    return value


def put(
    model: str,
    messages: list[dict[str, Any]],
    response_model_name: str,
    value: Any,
) -> None:
    """Store ``value`` under the request key. Evicts oldest if over capacity."""
    if not settings.classifier_cache_enabled:
        return
    k = _key(model, messages, response_model_name)
    expires_at = time.time() + settings.classifier_cache_ttl_seconds
    _CACHE[k] = (expires_at, value)
    _CACHE.move_to_end(k)
    while len(_CACHE) > settings.classifier_cache_max_entries:
        _CACHE.popitem(last=False)


def clear() -> None:
    """Drop all entries. Used by tests via the autouse fixture."""
    global _HITS, _MISSES
    _CACHE.clear()
    _HITS = 0
    _MISSES = 0


def stats() -> dict[str, int]:
    return {"size": len(_CACHE), "hits": _HITS, "misses": _MISSES}
