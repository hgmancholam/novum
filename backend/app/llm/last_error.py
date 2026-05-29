"""In-process last-error tracker for LLM providers (passive health signal).

The Anthropic health probe is deliberately key-only — a 30 s network
pinger would burn tokens without adding signal (see
``app.health.probes._anthropic_runner``). To still surface real outages
(rate-limit, quota exhaustion, auth failure, network error) on the
observability bar, ``llm.client`` pushes the kind of every recent
failure here, and the probe consults this tracker before returning
``ok``.

The tracker is intentionally trivial:
- Process-local state (single-worker uvicorn — RF-05).
- A successful call ``clear``\\ s the entry; otherwise the recorded
  error decays after ``DEFAULT_WINDOW_S`` so the bar recovers on its
  own when no further calls happen.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Literal

ProviderErrorKind = Literal["auth", "rate_limit", "quota", "unreachable", "upstream"]

DEFAULT_WINDOW_S: float = 300.0


@dataclass(frozen=True)
class ProviderError:
    provider: str
    kind: ProviderErrorKind
    message: str
    recorded_at: float


_lock = Lock()
_last_errors: dict[str, ProviderError] = {}


def record(provider: str, kind: ProviderErrorKind, message: str) -> None:
    """Record (or overwrite) the most recent error for ``provider``."""
    with _lock:
        _last_errors[provider] = ProviderError(
            provider=provider,
            kind=kind,
            message=message[:500],
            recorded_at=time.time(),
        )


def clear(provider: str) -> None:
    """Forget any recorded error for ``provider`` (call after a success)."""
    with _lock:
        _last_errors.pop(provider, None)


def get_recent(
    provider: str, *, within_s: float = DEFAULT_WINDOW_S
) -> ProviderError | None:
    """Return the recorded error if it occurred within ``within_s`` seconds."""
    with _lock:
        err = _last_errors.get(provider)
    if err is None:
        return None
    if (time.time() - err.recorded_at) > within_s:
        return None
    return err


def reset_all() -> None:
    """Test helper: drop every recorded error."""
    with _lock:
        _last_errors.clear()
