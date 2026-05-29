/**
 * useCostAnalytics — TanStack Query hook for the cross-run cost dashboard.
 *
 * Per ESLint `import/no-restricted-paths`, data-fetching hooks may only
 * be consumed from `pages/`.
 */

import { useQuery } from "@tanstack/react-query";

import { fetchCostAnalytics } from "@/lib/api/costAnalytics";
import type {
  CostAnalyticsFilters,
  CostAnalyticsResponse,
} from "@/types/costAnalytics";

export const costAnalyticsQueryKey = (
  filters: CostAnalyticsFilters
): readonly ["cost-analytics", CostAnalyticsFilters] =>
  ["cost-analytics", filters] as const;

export function useCostAnalytics(filters: CostAnalyticsFilters = {}) {
  return useQuery<CostAnalyticsResponse>({
    queryKey: costAnalyticsQueryKey(filters),
    queryFn: ({ signal }) => fetchCostAnalytics(filters, { signal }),
    staleTime: 60_000,
  });
}
