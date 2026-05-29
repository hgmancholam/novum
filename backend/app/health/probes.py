"""Per-service health probes (BRD-27 §4.8 / IP-27 Task 1.3).

Each probe is an ``async`` callable that **succeeds silently** when the
service is reachable and **raises** one of the probe-local exceptions
below otherwise. The :class:`HealthRegistry` is responsible for mapping
those exceptions to a :class:`ServiceStatus`; probes never assemble a
``ServiceHealth`` directly. This keeps the mapping table (BRD-27 §4.8)
in a single place.

V1 scope (BRD-27 §10):
- Anthropic: env-var presence check (no network — usage during a real
  research run is the canonical "live" probe; a 30 s health pinger
  would only add token spend without improving signal).
- Tavily / Wikipedia / Semantic Scholar / OpenAlex: reuse the existing
  ``Source.health_check()`` seam.
- Postgres: 500 ms ``SELECT 1`` round-trip.
- OpenAI / Gemini / GitHub Models: static ``DisabledError`` — wired-but-
  disabled providers are surfaced for transparency, never probed.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import NamedTuple

import structlog
from sqlalchemy import text

from app.config import settings
from app.database import async_session_maker
from app.domain.enums import SourceType
from app.health.models import ServiceCategory
from app.sources.registry import get_registry as get_source_registry

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Probe-local exception taxonomy (BRD-27 §4.8).
# Kept internal to ``app/health``; never raised by the route handler.
# ---------------------------------------------------------------------------


class _ProbeError(Exception):
    """Base class for probe-local exceptions."""


class NoKeyError(_ProbeError):
    """Required environment variable is missing."""

    def __init__(self, var_name: str) -> None:
        self.var_name = var_name
        super().__init__(f"missing {var_name}")


class AuthError(_ProbeError):
    """Upstream rejected the credentials (HTTP 401/403)."""


class RateLimitError(_ProbeError):
    """Upstream returned HTTP 429."""


class UnreachableError(_ProbeError):
    """Network-level failure: DNS, connection refused, TLS error."""


class UpstreamError(_ProbeError):
    """Upstream returned a non-success HTTP code (typically 5xx)."""

    def __init__(self, code: int | str) -> None:
        self.code = code
        super().__init__(f"upstream error: {code}")


class DisabledError(_ProbeError):
    """Service is intentionally not enabled in this V1 build."""

    def __init__(self, reason: str = "not enabled in V1") -> None:
        super().__init__(reason)


# ---------------------------------------------------------------------------
# ProbeSpec — what the registry iterates over.
# ---------------------------------------------------------------------------


ProbeRunner = Callable[[], Awaitable[None]]


class ProbeSpec(NamedTuple):
    """Static description of one probe.

    ``ttl_s`` overrides the registry's default cache TTL for this probe.
    Use it to throttle expensive or rate-limited services (Tavily, S2)
    while keeping cheap probes (Postgres) responsive.
    ``None`` means "use the registry's CACHE_TTL_S default".
    """

    id: str
    name: str
    category: ServiceCategory
    runner: ProbeRunner
    ttl_s: float | None = None


# ---------------------------------------------------------------------------
# Concrete runners.
# ---------------------------------------------------------------------------


async def _anthropic_runner() -> None:
    """Env-var presence check + passive last-error consult.

    V1 deliberately avoids an outbound network probe (would burn tokens
    every 30 s for no extra signal). Instead, ``app.llm.client`` records
    the kind of any recent Anthropic failure in
    ``app.llm.last_error``; we read that here so the bar reflects real
    outages (rate-limit, quota exhaustion, auth failure, network error)
    without spending tokens. A successful call clears the record, so
    the bar self-recovers as soon as the provider is healthy again.
    """
    if settings.anthropic_api_key is None:
        raise NoKeyError("ANTHROPIC_API_KEY")
    secret = settings.anthropic_api_key.get_secret_value()
    if not secret.strip():
        raise NoKeyError("ANTHROPIC_API_KEY")

    from app.llm import last_error as provider_health

    recent = provider_health.get_recent("anthropic")
    if recent is None:
        return
    snippet = recent.message[:160]
    if recent.kind == "auth":
        raise AuthError(snippet)
    if recent.kind == "rate_limit":
        raise RateLimitError(snippet)
    if recent.kind == "quota":
        raise UpstreamError(f"quota exhausted: {snippet}")
    if recent.kind == "unreachable":
        raise UnreachableError(snippet)
    raise UpstreamError(snippet)


def _make_disabled_runner(reason: str = "not enabled in V1") -> ProbeRunner:
    async def _runner() -> None:
        raise DisabledError(reason)

    return _runner


def _make_source_runner(source_type: SourceType, key_var: str | None) -> ProbeRunner:
    """Build a probe runner backed by ``Source.health_check()``.

    ``key_var`` is the env-var name to attribute a ``NoKeyError`` to
    when the registry has gated the source out (e.g. Tavily).
    """

    async def _runner() -> None:
        registry = get_source_registry()
        if source_type not in registry.types():
            if key_var is not None:
                raise NoKeyError(key_var)
            raise DisabledError(f"{source_type.value} not registered")
        source = registry.get(source_type)
        try:
            ok = await source.health_check()
        except asyncio.TimeoutError:
            raise
        except Exception as exc:  # noqa: BLE001 — boundary mapping
            _raise_mapped(exc)
        if not ok:
            raise UpstreamError("health_check returned False")

    return _runner


async def _postgres_runner() -> None:
    """500 ms ``SELECT 1`` round-trip."""
    try:
        async with async_session_maker() as session:
            await asyncio.wait_for(
                session.execute(text("SELECT 1")),
                timeout=0.5,
            )
    except asyncio.TimeoutError:
        raise
    except Exception as exc:  # noqa: BLE001 — boundary mapping
        _raise_mapped(exc)


# ---------------------------------------------------------------------------
# Exception mapping helper (boundary between SDK errors and probe taxonomy).
# ---------------------------------------------------------------------------


def _raise_mapped(exc: BaseException) -> None:
    """Translate an arbitrary SDK exception into a probe-local one."""
    name = type(exc).__name__.lower()
    msg = str(exc).lower()

    # HTTP code extraction (best-effort: many SDKs attach ``status_code``).
    status: int | None = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        if response is not None:
            status = getattr(response, "status_code", None)

    if status in (401, 403) or "unauthorized" in msg or "forbidden" in msg or "authentication" in msg:
        raise AuthError("authentication failed") from exc
    if status == 429 or "rate limit" in msg or "too many requests" in msg:
        raise RateLimitError("rate limited") from exc
    if (status is not None and 500 <= status < 600) or "server error" in msg:
        raise UpstreamError(status if status is not None else "5xx") from exc
    if (
        "connect" in name
        or "dns" in name
        or "ssl" in name
        or "tls" in name
        or "connection" in msg
        or "name or service not known" in msg
        or "operationalerror" in name
    ):
        raise UnreachableError("unreachable") from exc

    # Unknown — let the registry classify it as a generic ``down``.
    raise UpstreamError(status if status is not None else "unknown") from exc


# ---------------------------------------------------------------------------
# Probe registry (order = display order within each category).
# ---------------------------------------------------------------------------


PROBES: tuple[ProbeSpec, ...] = (
    # LLM family
    ProbeSpec(
        "anthropic", "Anthropic", ServiceCategory.LLM, _anthropic_runner,
        ttl_s=30.0,  # env-var + last-error tracker; cheap, refresh fast.
    ),
    ProbeSpec("openai", "OpenAI", ServiceCategory.LLM, _make_disabled_runner(), ttl_s=3600.0),
    ProbeSpec("gemini", "Gemini", ServiceCategory.LLM, _make_disabled_runner(), ttl_s=3600.0),
    ProbeSpec(
        "github_models",
        "GitHub Models",
        ServiceCategory.LLM,
        _make_disabled_runner(),
        ttl_s=3600.0,
    ),
    # Search
    ProbeSpec(
        "tavily",
        "Tavily",
        ServiceCategory.SEARCH,
        _make_source_runner(SourceType.TAVILY, "TAVILY_API_KEY"),
        ttl_s=600.0,  # paid quota: minimize probe cost (~4 k/month vs 86 k).
    ),
    # Knowledge
    ProbeSpec(
        "wikipedia",
        "Wikipedia",
        ServiceCategory.KNOWLEDGE,
        _make_source_runner(SourceType.WIKIPEDIA, None),
        ttl_s=120.0,
    ),
    ProbeSpec(
        "semantic_scholar",
        "Semantic Scholar",
        ServiceCategory.KNOWLEDGE,
        _make_source_runner(SourceType.SEMANTIC_SCHOLAR, None),
        ttl_s=300.0,  # aggressive RPS limit even with API key.
    ),
    ProbeSpec(
        "openalex",
        "OpenAlex",
        ServiceCategory.KNOWLEDGE,
        _make_source_runner(SourceType.OPENALEX, None),
        ttl_s=120.0,
    ),
    # Storage
    ProbeSpec(
        "postgres", "PostgreSQL", ServiceCategory.STORAGE, _postgres_runner,
        ttl_s=30.0,  # local + critical: detect outages fast.
    ),
)
