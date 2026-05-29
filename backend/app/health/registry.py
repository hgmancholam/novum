"""HealthRegistry — in-process singleton with 30 s cache + single-flight.

Public API (BRD-27 §4.9):
    snapshot() -> HealthSnapshot     # cache-aware
    refresh()  -> HealthSnapshot     # forces re-probe

Concurrency model (RF-05):
    * One ``anyio.Lock`` guards the cache pointer + inflight slot.
      It is **never** held across a probe round.
    * The initiator of a refresh creates an ``asyncio.Future`` and
      runs the probe round inline. Concurrent requests arriving while
      a refresh is in flight await the same future (single-flight,
      AC-02) — they receive ``cached=True`` while the initiator
      receives ``cached=False``.
    * Each probe runs under ``asyncio.wait_for(PROBE_TIMEOUT_S)`` so
      a stuck upstream cannot stall the snapshot.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from time import monotonic

import anyio
import structlog

from app.health.models import (
    HealthSnapshot,
    ServiceHealth,
    ServiceStatus,
)
from app.health.probes import (
    PROBES,
    AuthError,
    DisabledError,
    NoKeyError,
    ProbeSpec,
    RateLimitError,
    UnreachableError,
    UpstreamError,
)

logger = structlog.get_logger(__name__)


class HealthRegistry:
    """Process-local cache of the most recent :class:`HealthSnapshot`."""

    CACHE_TTL_S: float = 30.0
    PROBE_TIMEOUT_S: float = 2.0
    LATENCY_DEGRADED_MS: int = 1500

    def __init__(self, probes: tuple[ProbeSpec, ...] = PROBES) -> None:
        self._probes = probes
        self._cache: HealthSnapshot | None = None
        self._cache_ts: float = 0.0
        self._inflight: asyncio.Future[HealthSnapshot] | None = None
        self._lock = anyio.Lock()

    # -- public API --------------------------------------------------------

    async def snapshot(self) -> HealthSnapshot:
        """Return the cached snapshot or coalesce onto an in-flight refresh."""
        cached = await self._fast_cache_hit()
        if cached is not None:
            return cached
        return await self._refresh_or_join()

    async def refresh(self) -> HealthSnapshot:
        """Bypass the cache and force a fresh probe round."""
        async with self._lock:
            self._cache = None
            self._cache_ts = 0.0
        return await self._refresh_or_join()

    # -- internals ---------------------------------------------------------

    async def _fast_cache_hit(self) -> HealthSnapshot | None:
        async with self._lock:
            if (
                self._cache is not None
                and (monotonic() - self._cache_ts) < self.CACHE_TTL_S
            ):
                return self._cache.model_copy(update={"cached": True})
            return None

    async def _refresh_or_join(self) -> HealthSnapshot:
        initiator = False
        async with self._lock:
            # Double-check after lock: another waiter may have populated
            # the cache between the fast-path check and this point.
            if (
                self._cache is not None
                and (monotonic() - self._cache_ts) < self.CACHE_TTL_S
            ):
                return self._cache.model_copy(update={"cached": True})
            if self._inflight is None:
                loop = asyncio.get_running_loop()
                self._inflight = loop.create_future()
                inflight = self._inflight
                initiator = True
            else:
                inflight = self._inflight

        if initiator:
            await self._do_refresh(inflight)

        snap = await inflight
        if initiator:
            return snap
        return snap.model_copy(update={"cached": True})

    async def _do_refresh(self, fut: asyncio.Future[HealthSnapshot]) -> None:
        try:
            snap = await self._run_all_probes()
        except BaseException as exc:  # pragma: no cover — defensive
            async with self._lock:
                if self._inflight is fut:
                    self._inflight = None
            if not fut.done():
                fut.set_exception(exc)
            return
        async with self._lock:
            self._cache = snap
            self._cache_ts = monotonic()
            if self._inflight is fut:
                self._inflight = None
        if not fut.done():
            fut.set_result(snap)

    async def _run_all_probes(self) -> HealthSnapshot:
        results = await asyncio.gather(
            *(self._run_one(spec) for spec in self._probes),
            return_exceptions=False,
        )
        return HealthSnapshot(
            checked_at=datetime.now(timezone.utc),
            cached=False,
            services=list(results),
        )

    async def _run_one(self, spec: ProbeSpec) -> ServiceHealth:
        now = datetime.now(timezone.utc)
        t0 = monotonic()
        try:
            await asyncio.wait_for(spec.runner(), timeout=self.PROBE_TIMEOUT_S)
            latency_ms = int((monotonic() - t0) * 1000)
            if latency_ms > self.LATENCY_DEGRADED_MS:
                return ServiceHealth(
                    id=spec.id,
                    name=spec.name,
                    category=spec.category,
                    status=ServiceStatus.DEGRADED,
                    latency_ms=latency_ms,
                    message=f"high latency: {latency_ms}ms",
                    checked_at=now,
                )
            return ServiceHealth(
                id=spec.id,
                name=spec.name,
                category=spec.category,
                status=ServiceStatus.OK,
                latency_ms=latency_ms,
                message=None,
                checked_at=now,
            )
        except asyncio.TimeoutError:
            return self._fail(spec, now, ServiceStatus.DOWN, "probe timeout")
        except DisabledError as exc:
            return self._fail(spec, now, ServiceStatus.DISABLED, str(exc))
        except NoKeyError as exc:
            return self._fail(spec, now, ServiceStatus.NO_KEY, str(exc))
        except AuthError:
            return self._fail(spec, now, ServiceStatus.DOWN, "authentication failed")
        except RateLimitError:
            return self._fail(spec, now, ServiceStatus.DEGRADED, "rate limited")
        except UnreachableError:
            return self._fail(spec, now, ServiceStatus.DOWN, "unreachable")
        except UpstreamError as exc:
            return self._fail(spec, now, ServiceStatus.DOWN, str(exc))
        except Exception as exc:  # noqa: BLE001 — last-resort defense
            logger.warning(
                "health_probe_unhandled_exception",
                probe=spec.id,
                error_type=type(exc).__name__,
            )
            return self._fail(spec, now, ServiceStatus.DOWN, "internal probe error")

    @staticmethod
    def _fail(
        spec: ProbeSpec,
        when: datetime,
        status: ServiceStatus,
        message: str,
    ) -> ServiceHealth:
        return ServiceHealth(
            id=spec.id,
            name=spec.name,
            category=spec.category,
            status=status,
            latency_ms=None,
            message=message,
            checked_at=when,
        )


# ---------------------------------------------------------------------------
# Module-level singleton accessor (mirrors ``app.sources.registry``).
# ---------------------------------------------------------------------------


_registry: HealthRegistry | None = None


def get_registry() -> HealthRegistry:
    global _registry
    if _registry is None:
        _registry = HealthRegistry()
    return _registry


def reset_registry() -> None:
    """Clear the cached registry (test-only)."""
    global _registry
    _registry = None


__all__ = [
    "HealthRegistry",
    "get_registry",
    "reset_registry",
]
