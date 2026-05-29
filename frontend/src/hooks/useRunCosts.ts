/**
 * useRunCosts — TanStack Query hook for the cost ledger (BRD-29 §4.6.1).
 *
 * Loads `GET /api/runs/{runId}/costs` once on mount and caches the result.
 * Live updates happen by the container subscribing to the existing SSE
 * stream and pushing each `CostIncurred` frame into the cache via
 * `applyCostEvent` (or directly with `patchCosts` via the queryClient).
 *
 * Per `eslint.config.js`, this hook is data-fetching — only `pages/` may
 * import it. Organisms receive the resolved data via props.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";

import { fetchRunCosts } from "@/lib/api/costs";
import type {
  CostKind,
  ProviderCostRow,
  RunCostsResponse,
} from "@/types/costs";

export const runCostsQueryKey = (
  runId: string
): readonly ["runs", string, "costs"] => ["runs", runId, "costs"] as const;

export interface CostEventLike {
  type: string;
  provider?: string;
  kind?: string;
  model?: string | null;
  prompt_tokens?: number;
  completion_tokens?: number;
  units?: number;
  cost_usd?: number;
}

export interface UseRunCostsTotals {
  usd: number;
  promptTokens: number;
  completionTokens: number;
}

export interface UseRunCostsReturn {
  total: UseRunCostsTotals;
  rows: readonly ProviderCostRow[];
  isLoading: boolean;
  isError: boolean;
  refetch: () => void;
  applyCostEvent: (event: CostEventLike) => void;
}

function emptyResponse(runId: string): RunCostsResponse {
  return {
    run_id: runId,
    total_usd: 0,
    total_prompt_tokens: 0,
    total_completion_tokens: 0,
    by_provider: [],
  };
}

function isCostKind(value: unknown): value is CostKind {
  return value === "llm" || value === "search" || value === "fetch";
}

/**
 * Pure reducer — append a single CostIncurred event into a cached
 * `RunCostsResponse` and recompute totals + percentages. Exported for
 * unit tests and for container-side cache patching via `setQueryData`.
 */
export function patchCosts(
  prev: RunCostsResponse | undefined,
  event: CostEventLike,
  runId?: string
): RunCostsResponse {
  const base: RunCostsResponse =
    prev !== undefined ? prev : emptyResponse(runId ?? "");

  if (!isCostKind(event.kind) || typeof event.provider !== "string") {
    return base;
  }
  const model = event.model ?? null;
  const provider = event.provider;
  const kind = event.kind;
  const cost = event.cost_usd ?? 0;
  const promptTokens = event.prompt_tokens ?? 0;
  const completionTokens = event.completion_tokens ?? 0;
  const units = event.units ?? 0;

  const rows = base.by_provider.map((r) => ({ ...r }));
  const existingIdx = rows.findIndex(
    (r) => r.provider === provider && r.kind === kind && r.model === model
  );
  if (existingIdx >= 0) {
    const row = rows[existingIdx];
    if (row !== undefined) {
      rows[existingIdx] = {
        ...row,
        calls: row.calls + 1,
        prompt_tokens: row.prompt_tokens + promptTokens,
        completion_tokens: row.completion_tokens + completionTokens,
        units: row.units + units,
        cost_usd: row.cost_usd + cost,
      };
    }
  } else {
    rows.push({
      provider,
      kind,
      model,
      calls: 1,
      prompt_tokens: promptTokens,
      completion_tokens: completionTokens,
      units,
      cost_usd: cost,
      pct_of_total: 0,
    });
  }

  const totalUsd = rows.reduce((s, r) => s + r.cost_usd, 0);
  const totalPromptTokens = rows.reduce((s, r) => s + r.prompt_tokens, 0);
  const totalCompletionTokens = rows.reduce(
    (s, r) => s + r.completion_tokens,
    0
  );

  const withPct = rows
    .map((r) => ({
      ...r,
      pct_of_total:
        totalUsd > 0
          ? Math.round((r.cost_usd / totalUsd) * 10_000) / 100
          : 0,
    }))
    .sort((a, b) => b.cost_usd - a.cost_usd);

  return {
    run_id: base.run_id || (runId ?? ""),
    total_usd: totalUsd,
    total_prompt_tokens: totalPromptTokens,
    total_completion_tokens: totalCompletionTokens,
    by_provider: withPct,
  };
}

export function useRunCosts(runId: string | undefined): UseRunCostsReturn {
  const queryClient = useQueryClient();
  const enabled = typeof runId === "string" && runId.length > 0;
  const key = runCostsQueryKey(runId ?? "__noop__");

  const query = useQuery<RunCostsResponse>({
    queryKey: key,
    queryFn: () => {
      if (!enabled) {
        throw new Error("runId is required");
      }
      return fetchRunCosts(runId ?? "");
    },
    enabled,
    staleTime: 30 * 1000,
  });

  const applyCostEvent = useCallback(
    (event: CostEventLike): void => {
      if (!enabled || event.type !== "CostIncurred") {
        return;
      }
      queryClient.setQueryData<RunCostsResponse>(key, (prev) =>
        patchCosts(prev, event, runId)
      );
    },
    [enabled, queryClient, key, runId]
  );

  const data = query.data;
  const total: UseRunCostsTotals = {
    usd: data?.total_usd ?? 0,
    promptTokens: data?.total_prompt_tokens ?? 0,
    completionTokens: data?.total_completion_tokens ?? 0,
  };

  return {
    total,
    rows: data?.by_provider ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
    refetch: () => {
      void query.refetch();
    },
    applyCostEvent,
  };
}
