"""Service-health observability package (BRD-27 / IP-27).

In-process registry that probes each integrated external service
(Anthropic, Tavily, Wikipedia, Semantic Scholar, OpenAlex, Postgres)
on demand and serves a cached aggregated snapshot to the frontend
``ServiceStatusBar`` via ``GET /api/health/services``.

The registry is a process-local singleton (RF-05 single-server) and
runs every probe under ``asyncio.wait_for(PROBE_TIMEOUT_S)`` so a
misbehaving upstream cannot stall the snapshot.
"""

from app.health.models import (
    HealthSnapshot,
    ServiceCategory,
    ServiceHealth,
    ServiceStatus,
)
from app.health.registry import HealthRegistry, get_registry

__all__ = [
    "HealthRegistry",
    "HealthSnapshot",
    "ServiceCategory",
    "ServiceHealth",
    "ServiceStatus",
    "get_registry",
]
