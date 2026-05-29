/**
 * Cost ledger response types (BRD-29 / IP-29).
 *
 * These mirror the FastAPI response schema returned by
 * `GET /api/runs/{run_id}/costs` (backend: `app/routes/costs.py`).
 * Keys stay snake_case to match the wire format — no transform layer.
 */

export type CostKind = "llm" | "search" | "fetch";

export interface ProviderCostRow {
  provider: string;
  kind: CostKind;
  model: string | null;
  calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  units: number;
  cost_usd: number;
  pct_of_total: number;
}

export interface RunCostsResponse {
  run_id: string;
  total_usd: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  by_provider: ProviderCostRow[];
}
