/**
 * useServiceHealth — periodic poller for `GET /api/health/services` (BRD-27 §4.6).
 *
 * Single source of truth for the footer status bar. TanStack Query handles
 * - 60 s background refetch (AC-02),
 * - silent failure (no toast, no error banner),
 * - `keepPreviousData` so the bar never flashes during a refetch.
 */

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { getServiceHealth } from "@/lib/api";
import type { HealthSnapshot } from "@/types/health";

export const SERVICE_HEALTH_QUERY_KEY = ["health", "services"] as const;

export function useServiceHealth() {
  return useQuery<HealthSnapshot>({
    queryKey: SERVICE_HEALTH_QUERY_KEY,
    queryFn: ({ signal }) => getServiceHealth({ signal }),
    refetchInterval: 60_000,
    refetchOnWindowFocus: false,
    staleTime: 30_000,
    placeholderData: keepPreviousData,
    retry: 1,
  });
}
