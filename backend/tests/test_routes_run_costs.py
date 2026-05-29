"""Integration tests for ``GET /api/runs/{run_id}/costs`` (BRD-29 §4.3)."""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.run import Run

pytestmark = pytest.mark.asyncio


async def _seed_run(session: AsyncSession, owner: str) -> uuid.UUID:
    run = Run(
        owner_username=owner,
        question="What is X?",
        output_format="prose",
        confidence_threshold=0.7,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run.id


async def _install_run_costs_table(session: AsyncSession) -> None:
    """Create a SQLite-compatible stand-in for the PG view used by the route."""
    await session.execute(sa.text("DROP TABLE IF EXISTS run_costs"))
    await session.execute(sa.text(
        """
        CREATE TABLE run_costs (
            run_id            TEXT,
            provider          TEXT,
            kind              TEXT,
            model             TEXT,
            task_name         TEXT,
            call_count        INTEGER,
            prompt_tokens     INTEGER,
            completion_tokens INTEGER,
            units             INTEGER,
            cost_usd          REAL,
            latency_ms_total  INTEGER
        )
        """
    ))


async def test_unauthenticated_returns_401(client: AsyncClient) -> None:
    res = await client.get(f"/api/runs/{uuid.uuid4()}/costs")
    assert res.status_code == 401


async def test_unknown_run_returns_404(
    client: AsyncClient, seeded_user: str, auth_headers: dict[str, str]
) -> None:
    res = await client.get(
        f"/api/runs/{uuid.uuid4()}/costs", headers=auth_headers
    )
    assert res.status_code == 404


async def test_non_owner_returns_404(
    client: AsyncClient,
    seeded_user: str,
    auth_headers: dict[str, str],
    sqlite_session: AsyncSession,
) -> None:
    from app.services.auth_service import AuthService

    service = AuthService(sqlite_session)
    await service.register("someone_else")
    other_run_id = await _seed_run(sqlite_session, "someone_else")

    res = await client.get(
        f"/api/runs/{other_run_id}/costs", headers=auth_headers
    )
    assert res.status_code == 404


async def test_empty_costs_returns_zero_totals(
    client: AsyncClient,
    seeded_user: str,
    auth_headers: dict[str, str],
    sqlite_session: AsyncSession,
) -> None:
    pytest.importorskip("psycopg2", reason="route binds UUID; SQLite cannot")
    run_id = await _seed_run(sqlite_session, seeded_user)
    await _install_run_costs_table(sqlite_session)
    await sqlite_session.commit()

    res = await client.get(f"/api/runs/{run_id}/costs", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["run_id"] == str(run_id)
    assert body["total_cost_usd"] == 0.0
    assert body["total_calls"] == 0
    assert body["rows"] == []


async def test_aggregated_costs_compute_pct(
    client: AsyncClient,
    seeded_user: str,
    auth_headers: dict[str, str],
    sqlite_session: AsyncSession,
) -> None:
    pytest.importorskip("psycopg2", reason="route binds UUID; SQLite cannot")
    run_id = await _seed_run(sqlite_session, seeded_user)
    await _install_run_costs_table(sqlite_session)
    await sqlite_session.execute(sa.text(
        "INSERT INTO run_costs VALUES "
        "(:r, 'anthropic', 'llm', 'claude-sonnet-4-6', 'classify', 2, 1000, 200, 0, 0.03, 1500), "
        "(:r, 'tavily', 'search', NULL, NULL, 1, 0, 0, 2, 0.016, 400)"
    ), {"r": str(run_id)})
    await sqlite_session.commit()

    res = await client.get(f"/api/runs/{run_id}/costs", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["total_cost_usd"] == pytest.approx(0.046)
    assert body["total_prompt_tokens"] == 1000
    assert body["total_completion_tokens"] == 200
    assert body["total_calls"] == 3
    assert len(body["rows"]) == 2

    # Highest cost first.
    assert body["rows"][0]["provider"] == "anthropic"
    assert body["rows"][0]["pct_of_total"] == pytest.approx(
        round(0.03 / 0.046 * 100.0, 2)
    )
    assert body["rows"][1]["provider"] == "tavily"
