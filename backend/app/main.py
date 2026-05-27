"""FastAPI application entry point."""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.runner import agent_runner
from app.config import settings
from app.database import engine
from app.routes import api_router

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown."""
    logger.info("starting_novum", host=settings.host, port=settings.port)
    # BRD-19 §4.2: the runner's registry is process-local; multiple workers
    # would silently bypass single-writer-per-run. Surface the misconfig.
    web_concurrency = os.environ.get("WEB_CONCURRENCY", "1")
    if web_concurrency != "1":
        logger.error(
            "multiple_workers_detected",
            web_concurrency=web_concurrency,
            hint="AgentRunner is single-loop; run uvicorn with --workers 1",
        )
    yield
    await agent_runner.shutdown()
    await engine.dispose()
    logger.info("shutdown_complete")


app = FastAPI(
    title="Novum API",
    description="Self-directing research agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
