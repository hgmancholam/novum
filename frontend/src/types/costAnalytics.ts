/**
 * Cross-run cost analytics types — mirror of
 * `backend/app/routes/cost_analytics.py` response model.
 */

export interface AnalyticsTotals {
  cost_usd: number;
  prompt_tokens: number;
  completion_tokens: number;
  calls: number;
  runs: number;
}

export interface ProviderBreakdown {
  provider: string;
  cost_usd: number;
  calls: number;
  tokens: number;
  pct_of_total: number;
}

export interface KindBreakdown {
  kind: string;
  cost_usd: number;
  calls: number;
  tokens: number;
}

export interface ModelBreakdown {
  provider: string;
  model: string;
  cost_usd: number;
  calls: number;
  tokens: number;
}

export interface DailyPoint {
  /** ISO date `YYYY-MM-DD`. */
  date: string;
  cost_usd: number;
  calls: number;
  tokens: number;
}

export interface CostRow {
  run_id: string;
  question: string;
  /** ISO datetime. */
  occurred_at: string;
  provider: string;
  kind: string;
  model: string | null;
  task_name: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: number;
}

export interface CostAnalyticsResponse {
  date_from: string;
  date_to: string;
  totals: AnalyticsTotals;
  by_provider: ProviderBreakdown[];
  by_kind: KindBreakdown[];
  by_model: ModelBreakdown[];
  by_day: DailyPoint[];
  rows: CostRow[];
}

export interface CostAnalyticsFilters {
  dateFrom?: string;
  dateTo?: string;
  providers?: string[];
  kinds?: string[];
  rowLimit?: number;
}
