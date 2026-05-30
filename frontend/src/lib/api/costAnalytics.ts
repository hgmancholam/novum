/**
 * Cross-run cost analytics API client.
 *
 * Wraps `GET /api/costs/analytics`. Uses shared `api` helper (API_URL prefix
 * — L-008) and merges auth headers after `...init` (L-009).
 */

import { api } from "@/lib/api";
import { getAuthHeaders } from "@/lib/auth";
import type {
  CostAnalyticsFilters,
  CostAnalyticsResponse,
} from "@/types/costAnalytics";

function buildQuery(filters: CostAnalyticsFilters): string {
  const params = new URLSearchParams();
  if (filters.dateFrom) params.set("date_from", filters.dateFrom);
  if (filters.dateTo) params.set("date_to", filters.dateTo);
  for (const p of filters.providers ?? []) {
    if (p) params.append("provider", p);
  }
  for (const k of filters.kinds ?? []) {
    if (k) params.append("kind", k);
  }
  for (const o of filters.owners ?? []) {
    if (o) params.append("owner", o);
  }
  if (filters.rowLimit) params.set("row_limit", String(filters.rowLimit));
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export async function fetchCostAnalytics(
  filters: CostAnalyticsFilters = {},
  init?: RequestInit
): Promise<CostAnalyticsResponse> {
  return api.get<CostAnalyticsResponse>(
    `/api/costs/analytics${buildQuery(filters)}`,
    {
      ...init,
      // eslint-disable-next-line @typescript-eslint/no-misused-spread
      headers: { ...getAuthHeaders(), ...init?.headers },
    }
  );
}
