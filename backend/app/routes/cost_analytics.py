"""Cross-run cost analytics endpoint.

Aggregates `CostIncurred` events across **all** runs owned by the current
user, with optional date / provider / kind filters. Powers the
`/costs` dashboard page (cross-cutting, not per-run).

Pure read endpoint — no mutations.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.types import String

from app.dependencies import CurrentUsername, DbSession

router = APIRouter(prefix="/api/costs", tags=["Costs"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class AnalyticsTotals(BaseModel):
    cost_usd: float
    prompt_tokens: int
    completion_tokens: int
    calls: int
    runs: int


class ProviderBreakdown(BaseModel):
    provider: str
    cost_usd: float
    calls: int
    tokens: int
    pct_of_total: float


class KindBreakdown(BaseModel):
    kind: str
    cost_usd: float
    calls: int
    tokens: int


class ModelBreakdown(BaseModel):
    provider: str
    model: str
    cost_usd: float
    calls: int
    tokens: int


class DailyPoint(BaseModel):
    date: date
    cost_usd: float
    calls: int
    tokens: int


class CostRow(BaseModel):
    run_id: str
    question: str
    occurred_at: datetime
    provider: str
    kind: str
    model: str | None
    task_name: str | None
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


class CostAnalyticsResponse(BaseModel):
    date_from: date
    date_to: date
    totals: AnalyticsTotals
    by_provider: list[ProviderBreakdown]
    by_kind: list[KindBreakdown]
    by_model: list[ModelBreakdown]
    by_day: list[DailyPoint]
    rows: list[CostRow]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/analytics", response_model=CostAnalyticsResponse)
async def get_cost_analytics(
    db: DbSession,
    username: CurrentUsername,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    provider: Annotated[list[str] | None, Query()] = None,
    kind: Annotated[list[str] | None, Query()] = None,
    row_limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> CostAnalyticsResponse:
    """Aggregate cost events across the current user's runs."""
    today = datetime.now(timezone.utc).date()
    df = date_from if date_from is not None else today - timedelta(days=30)
    dt = date_to if date_to is not None else today

    # Inclusive upper bound: convert dt → start of next day.
    range_start = datetime.combine(df, datetime.min.time(), tzinfo=timezone.utc)
    range_end = datetime.combine(
        dt + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc
    )

    where_parts = [
        "events.payload->>'type' = 'CostIncurred'",
        "runs.owner_username = :owner",
        "events.created_at >= :range_start",
        "events.created_at < :range_end",
    ]
    params: dict[str, object] = {
        "owner": username,
        "range_start": range_start,
        "range_end": range_end,
    }

    provider_filter = [p for p in (provider or []) if p]
    kind_filter = [k for k in (kind or []) if k]
    if provider_filter:
        where_parts.append("events.payload->>'provider' = ANY(:providers)")
        params["providers"] = provider_filter
    if kind_filter:
        where_parts.append("events.payload->>'kind' = ANY(:kinds)")
        params["kinds"] = kind_filter

    where_clause = " AND ".join(where_parts)

    base_from = f"""
        FROM events
        JOIN runs ON runs.id = events.run_id
        WHERE {where_clause}
    """

    bindparams = []
    if provider_filter:
        bindparams.append(bindparam("providers", type_=ARRAY(String)))
    if kind_filter:
        bindparams.append(bindparam("kinds", type_=ARRAY(String)))

    def _stmt(sql: str):
        stmt = text(sql)
        if bindparams:
            stmt = stmt.bindparams(*bindparams)
        return stmt

    # --- Totals --------------------------------------------------------------
    totals_sql = f"""
        SELECT
            COALESCE(SUM((events.payload->>'cost_usd')::double precision), 0.0) AS cost_usd,
            COALESCE(SUM((events.payload->>'prompt_tokens')::bigint), 0)        AS prompt_tokens,
            COALESCE(SUM((events.payload->>'completion_tokens')::bigint), 0)    AS completion_tokens,
            COUNT(*)                                                            AS calls,
            COUNT(DISTINCT events.run_id)                                       AS runs
        {base_from}
    """
    totals_row = (await db.execute(_stmt(totals_sql), params)).mappings().one()
    totals = AnalyticsTotals(
        cost_usd=float(totals_row["cost_usd"]),
        prompt_tokens=int(totals_row["prompt_tokens"]),
        completion_tokens=int(totals_row["completion_tokens"]),
        calls=int(totals_row["calls"]),
        runs=int(totals_row["runs"]),
    )

    # --- By provider ---------------------------------------------------------
    provider_sql = f"""
        SELECT
            events.payload->>'provider' AS provider,
            COALESCE(SUM((events.payload->>'cost_usd')::double precision), 0.0) AS cost_usd,
            COUNT(*) AS calls,
            COALESCE(SUM(
                (events.payload->>'prompt_tokens')::bigint
              + (events.payload->>'completion_tokens')::bigint
            ), 0) AS tokens
        {base_from}
        GROUP BY events.payload->>'provider'
        ORDER BY cost_usd DESC
    """
    provider_rows = (await db.execute(_stmt(provider_sql), params)).mappings().all()
    total_cost = totals.cost_usd
    by_provider = [
        ProviderBreakdown(
            provider=str(r["provider"] or "unknown"),
            cost_usd=float(r["cost_usd"]),
            calls=int(r["calls"]),
            tokens=int(r["tokens"]),
            pct_of_total=round(
                (float(r["cost_usd"]) / total_cost * 100.0) if total_cost > 0 else 0.0,
                2,
            ),
        )
        for r in provider_rows
    ]

    # --- By kind -------------------------------------------------------------
    kind_sql = f"""
        SELECT
            events.payload->>'kind' AS kind,
            COALESCE(SUM((events.payload->>'cost_usd')::double precision), 0.0) AS cost_usd,
            COUNT(*) AS calls,
            COALESCE(SUM(
                (events.payload->>'prompt_tokens')::bigint
              + (events.payload->>'completion_tokens')::bigint
            ), 0) AS tokens
        {base_from}
        GROUP BY events.payload->>'kind'
        ORDER BY cost_usd DESC
    """
    kind_rows = (await db.execute(_stmt(kind_sql), params)).mappings().all()
    by_kind = [
        KindBreakdown(
            kind=str(r["kind"] or "unknown"),
            cost_usd=float(r["cost_usd"]),
            calls=int(r["calls"]),
            tokens=int(r["tokens"]),
        )
        for r in kind_rows
    ]

    # --- By model (top-N) ----------------------------------------------------
    model_sql = f"""
        SELECT
            events.payload->>'provider' AS provider,
            events.payload->>'model'    AS model,
            COALESCE(SUM((events.payload->>'cost_usd')::double precision), 0.0) AS cost_usd,
            COUNT(*) AS calls,
            COALESCE(SUM(
                (events.payload->>'prompt_tokens')::bigint
              + (events.payload->>'completion_tokens')::bigint
            ), 0) AS tokens
        {base_from}
        GROUP BY events.payload->>'provider', events.payload->>'model'
        ORDER BY cost_usd DESC
        LIMIT 10
    """
    model_rows = (await db.execute(_stmt(model_sql), params)).mappings().all()
    by_model = [
        ModelBreakdown(
            provider=str(r["provider"] or "unknown"),
            model=str(r["model"] or "—"),
            cost_usd=float(r["cost_usd"]),
            calls=int(r["calls"]),
            tokens=int(r["tokens"]),
        )
        for r in model_rows
    ]

    # --- By day --------------------------------------------------------------
    day_sql = f"""
        SELECT
            (events.created_at AT TIME ZONE 'UTC')::date AS day,
            COALESCE(SUM((events.payload->>'cost_usd')::double precision), 0.0) AS cost_usd,
            COUNT(*) AS calls,
            COALESCE(SUM(
                (events.payload->>'prompt_tokens')::bigint
              + (events.payload->>'completion_tokens')::bigint
            ), 0) AS tokens
        {base_from}
        GROUP BY day
        ORDER BY day ASC
    """
    day_rows = (await db.execute(_stmt(day_sql), params)).mappings().all()
    by_day = [
        DailyPoint(
            date=r["day"],
            cost_usd=float(r["cost_usd"]),
            calls=int(r["calls"]),
            tokens=int(r["tokens"]),
        )
        for r in day_rows
    ]

    # --- Rows (most recent first) -------------------------------------------
    rows_sql = f"""
        SELECT
            events.run_id::text       AS run_id,
            runs.question             AS question,
            events.created_at         AS occurred_at,
            events.payload->>'provider'  AS provider,
            events.payload->>'kind'      AS kind,
            events.payload->>'model'     AS model,
            events.payload->>'task_name' AS task_name,
            COALESCE((events.payload->>'prompt_tokens')::bigint, 0)     AS prompt_tokens,
            COALESCE((events.payload->>'completion_tokens')::bigint, 0) AS completion_tokens,
            COALESCE((events.payload->>'cost_usd')::double precision, 0.0) AS cost_usd
        {base_from}
        ORDER BY events.created_at DESC
        LIMIT :row_limit
    """
    rows_params = {**params, "row_limit": row_limit}
    raw_rows = (await db.execute(_stmt(rows_sql), rows_params)).mappings().all()
    rows = [
        CostRow(
            run_id=str(r["run_id"]),
            question=str(r["question"]),
            occurred_at=r["occurred_at"],
            provider=str(r["provider"] or "unknown"),
            kind=str(r["kind"] or "unknown"),
            model=(str(r["model"]) if r["model"] is not None else None),
            task_name=(str(r["task_name"]) if r["task_name"] is not None else None),
            prompt_tokens=int(r["prompt_tokens"]),
            completion_tokens=int(r["completion_tokens"]),
            cost_usd=float(r["cost_usd"]),
        )
        for r in raw_rows
    ]

    return CostAnalyticsResponse(
        date_from=df,
        date_to=dt,
        totals=totals,
        by_provider=by_provider,
        by_kind=by_kind,
        by_model=by_model,
        by_day=by_day,
        rows=rows,
    )
