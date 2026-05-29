"""Health endpoints.

Two routers:

* ``router`` — legacy liveness probe at ``/health`` (BRD-27 §10:
  deliberately untouched so deployment health-checks keep working).
* ``services_router`` — aggregated per-service health bar payload at
  ``/api/health/services`` (BRD-27 §4.5 / IP-27 Task 1.7).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.health.models import HealthSnapshot
from app.health.registry import get_registry

router = APIRouter(tags=["Health"])
services_router = APIRouter(prefix="/api/health", tags=["Health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — returns 200 with ``{"status": "ok"}``."""
    return {"status": "ok"}


@services_router.get("/services", response_model=HealthSnapshot)
async def service_health() -> HealthSnapshot:
    """Aggregated per-service health snapshot (cached 30 s server-side)."""
    return await get_registry().snapshot()
