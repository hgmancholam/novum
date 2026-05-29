"""API routes package."""

from __future__ import annotations

from fastapi import APIRouter

from app.routes.auth import router as auth_router
from app.routes.cost_analytics import router as cost_analytics_router
from app.routes.costs import router as costs_router
from app.routes.events import router as events_router
from app.routes.formats import router as formats_router
from app.routes.health import router as health_router
from app.routes.health import services_router as health_services_router
from app.routes.llm import router as llm_router
from app.routes.runs import router as runs_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(health_services_router)
api_router.include_router(auth_router)
api_router.include_router(runs_router)
api_router.include_router(events_router)
api_router.include_router(formats_router)
api_router.include_router(llm_router)
api_router.include_router(costs_router)
api_router.include_router(cost_analytics_router)

__all__ = ["api_router"]
