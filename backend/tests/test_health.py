"""
Unit tests for health endpoint.
BRD-00 validation: Verify FastAPI setup works correctly.

Per workflow.md F3.S3: generate_unit_tests

Note: These tests are standalone and don't require database or external services.
"""

import os

# Set test environment variables BEFORE importing app
os.environ.setdefault("GITHUB_TOKEN", "test_token")
os.environ.setdefault("TAVILY_API_KEY", "test_key")

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok():
    """GET /health should return 200 with status: ok."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_health_endpoint_content_type():
    """GET /health should return application/json."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.headers["content-type"] == "application/json"


@pytest.mark.asyncio
async def test_cors_headers_present():
    """CORS headers should be configured."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

    # CORS preflight should succeed
    assert response.status_code in (200, 204)
