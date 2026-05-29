"""Per-run cost summary endpoint (BRD-29 §4.3).

Aggregates the ``run_costs`` SQL view into a single response that the
frontend can render directly. Pure read endpoint — no mutations.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text

from app.dependencies import CurrentUsername, DbSession
from app.models.run import Run

router = APIRouter(prefix="/api/runs", tags=["Costs"])


class ProviderCostRow(BaseModel):
    provider: str
    kind: str
    model: str | None = None
    task_name: str | None = None
    call_count: int
    prompt_tokens: int
    completion_tokens: int
    units: int
    cost_usd: float
    latency_ms_total: int
    pct_of_total: float


class RunCostsResponse(BaseModel):
    run_id: UUID
    total_cost_usd: float
    total_prompt_tokens: int
    total_completion_tokens: int
    total_calls: int
    rows: list[ProviderCostRow]


@router.get("/{run_id}/costs", response_model=RunCostsResponse)
async def get_run_costs(
    run_id: UUID,
    db: DbSession,
    username: CurrentUsername,
) -> RunCostsResponse:
    """Return the per-provider/kind/model/task cost breakdown for a run."""
    run = await db.get(Run, run_id)
    if run is None or run.owner_username != username:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    result = await db.execute(
        text(
            """
            SELECT provider, kind, model, task_name,
                   call_count, prompt_tokens, completion_tokens,
                   units, cost_usd, latency_ms_total
            FROM run_costs
            WHERE run_id = :run_id
            ORDER BY cost_usd DESC, provider ASC, kind ASC
            """
        ),
        {"run_id": run_id},
    )
    raw_rows = result.mappings().all()

    total_cost = sum(float(r["cost_usd"]) for r in raw_rows)
    total_prompt = sum(int(r["prompt_tokens"]) for r in raw_rows)
    total_completion = sum(int(r["completion_tokens"]) for r in raw_rows)
    total_calls = sum(int(r["call_count"]) for r in raw_rows)

    rows: list[ProviderCostRow] = []
    for r in raw_rows:
        cost = float(r["cost_usd"])
        pct = (cost / total_cost * 100.0) if total_cost > 0.0 else 0.0
        rows.append(
            ProviderCostRow(
                provider=r["provider"],
                kind=r["kind"],
                model=r["model"],
                task_name=r["task_name"],
                call_count=int(r["call_count"]),
                prompt_tokens=int(r["prompt_tokens"]),
                completion_tokens=int(r["completion_tokens"]),
                units=int(r["units"]),
                cost_usd=cost,
                latency_ms_total=int(r["latency_ms_total"]),
                pct_of_total=round(pct, 2),
            )
        )

    return RunCostsResponse(
        run_id=run_id,
        total_cost_usd=total_cost,
        total_prompt_tokens=total_prompt,
        total_completion_tokens=total_completion,
        total_calls=total_calls,
        rows=rows,
    )
