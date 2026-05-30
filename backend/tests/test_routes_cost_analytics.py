"""Integration tests for ``GET /api/costs/analytics``.

The endpoint relies on PostgreSQL JSONB operators / casts that SQLite
cannot execute (`::double precision`, `ANY(:array)`, `AT TIME ZONE`).
The empty-data path is therefore gated behind ``psycopg2`` like the
sibling per-run test (`test_routes_run_costs.py`).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_unauthenticated_returns_401(client: AsyncClient) -> None:
    res = await client.get("/api/costs/analytics")
    assert res.status_code == 401


async def test_authenticated_empty_returns_zero_totals(
    client: AsyncClient,
    seeded_user: str,
    auth_headers: dict[str, str],
) -> None:
    pytest.importorskip(
        "psycopg2", reason="endpoint uses PG-only JSONB operators"
    )
    res = await client.get("/api/costs/analytics", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["totals"]["cost_usd"] == 0.0
    assert body["totals"]["calls"] == 0
    assert body["totals"]["runs"] == 0
    assert body["by_provider"] == []
    assert body["by_kind"] == []
    assert body["by_user"] == []
    assert body["by_model"] == []
    assert body["by_day"] == []
    assert body["rows"] == []
    assert "date_from" in body and "date_to" in body


async def test_filter_query_params_accepted(
    client: AsyncClient,
    seeded_user: str,
    auth_headers: dict[str, str],
) -> None:
    """Validate that the filter parameters are parsed without 422."""
    pytest.importorskip(
        "psycopg2", reason="endpoint uses PG-only JSONB operators"
    )
    res = await client.get(
        "/api/costs/analytics",
        params={
            "date_from": "2026-01-01",
            "date_to": "2026-12-31",
            "provider": ["anthropic", "tavily"],
            "kind": ["llm", "search"],
            "owner": ["alice", "bob"],
            "row_limit": 50,
        },
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["date_from"] == "2026-01-01"
    assert body["date_to"] == "2026-12-31"


async def test_invalid_row_limit_returns_422(
    client: AsyncClient,
    seeded_user: str,
    auth_headers: dict[str, str],
) -> None:
    res = await client.get(
        "/api/costs/analytics",
        params={"row_limit": 0},
        headers=auth_headers,
    )
    assert res.status_code == 422
