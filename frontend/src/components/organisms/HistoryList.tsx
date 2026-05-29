/**
 * HistoryList organism — presentational list with RF-09 / BRD-12 states.
 *
 * Task 2.0 (BRD-20): list-loop lives here in HistoryList.tsx;
 * HistoryItem replaces RunRow.
 *
 * State coverage (ui-prototype.md §3.2):
 *   L1 - Empty list
 *   L2 - List with items
 *   L3 - Item selected (handled per-row via `selectedRunId`)
 *   L4 - Item hover (handled in `RunRow` via CSS)
 *   L5 - Loading skeleton
 *   L6 - Error with retry
 *   L7 - Filtered (active filters + empty-after-filter message)
 *
 * Presentational: parent owns data fetching (ESLint forbids organisms from
 * importing `useRun*` hooks).
 */

import { useMemo } from "react";
import { AnimatePresence } from "motion/react";

import { Button, Spinner } from "@/components/atoms";
import { HistoryFilters, hasActiveFilters } from "./HistoryFilters";
import { HistoryItem } from "./HistoryItem";
import type { HistoryFilterValues, RunSummary } from "@/types/history";

export interface HistoryListProps {
  runs: readonly RunSummary[];
  selectedRunId: string | null;
  filters: HistoryFilterValues;
  onFiltersChange: (next: HistoryFilterValues) => void;
  onSelectRun: (runId: string) => void;
  onNewQuestion: () => void;
  onDeleteRun?: ((runId: string) => void) | undefined;

  isLoading: boolean;
  isError: boolean;
  errorMessage?: string;
  onRetry: () => void;

  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  onLoadMore: () => void;

  onRefresh?: () => void;
  isRefreshing?: boolean;
}

function applyFilters(
  runs: readonly RunSummary[],
  filters: HistoryFilterValues
): RunSummary[] {
  const search = filters.search?.trim().toLowerCase() ?? "";
  return runs.filter((run) => {
    if (filters.status !== undefined && run.status !== filters.status) {
      return false;
    }
    if (
      filters.stopReason !== undefined &&
      run.stopReason !== filters.stopReason
    ) {
      return false;
    }
    if (search !== "" && !run.question.toLowerCase().includes(search)) {
      return false;
    }
    return true;
  });
}

function SkeletonRow() {
  return (
    <div
      data-testid="run-row-skeleton"
      className="border-b border-[var(--glass-border)] px-3 py-3"
    >
      <div className="mb-2 h-3.5 w-3/4 animate-pulse rounded bg-[var(--bg-tertiary)]" />
      <div className="flex items-center justify-between">
        <div className="h-4 w-20 animate-pulse rounded-full bg-[var(--bg-tertiary)]" />
        <div className="h-3 w-12 animate-pulse rounded bg-[var(--bg-tertiary)]" />
      </div>
    </div>
  );
}

export function HistoryList({
  runs,
  selectedRunId,
  filters,
  onFiltersChange,
  onSelectRun,
  onNewQuestion,
  onDeleteRun,
  isLoading,
  isError,
  errorMessage,
  onRetry,
  hasNextPage,
  isFetchingNextPage,
  onLoadMore,
  onRefresh,
  isRefreshing,
}: HistoryListProps) {
  const filtered = useMemo(() => applyFilters(runs, filters), [runs, filters]);
  const filtersActive = hasActiveFilters(filters);

  // L6 — error
  if (isError && !isLoading) {
    return (
      <div
        data-testid="history-list"
        data-state="error"
        className="flex h-full flex-col items-center justify-center gap-3 px-4 py-8 text-center"
      >
        <p className="text-sm text-[var(--semantic-danger)]">
          {errorMessage ?? "Failed to load history."}
        </p>
        <Button variant="secondary" size="sm" onClick={onRetry}>
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div
      data-testid="history-list"
      data-state={
        isLoading
          ? "loading"
          : filtered.length === 0
            ? "empty"
            : "list"
      }
      className="flex h-full flex-col"
    >
      <HistoryFilters
        filters={filters}
        onChange={onFiltersChange}
        {...(onRefresh ? { onRefresh } : {})}
        {...(isRefreshing !== undefined ? { isRefreshing } : {})}
      />

      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div aria-busy="true" aria-live="polite">
            <SkeletonRow />
            <SkeletonRow />
            <SkeletonRow />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 px-4 py-10 text-center">
            <p className="text-sm text-[var(--text-secondary)]">
              {filtersActive
                ? "No runs match your filters."
                : "No research runs yet."}
            </p>
            <Button size="sm" onClick={onNewQuestion}>
              {filtersActive ? "New question" : "Start your first research"}
            </Button>
          </div>
        ) : (
          <ul className="flex flex-col" aria-label="Run history">
            <AnimatePresence initial={false}>
              {filtered.map((run) => (
                <HistoryItem
                  key={run.id}
                  run={run}
                  isSelected={run.id === selectedRunId}
                  onSelect={onSelectRun}
                  onDelete={onDeleteRun}
                />
              ))}
            </AnimatePresence>
            {hasNextPage ? (
              <li className="px-3 py-3">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onLoadMore}
                  loading={isFetchingNextPage}
                  className="w-full"
                >
                  {isFetchingNextPage ? "Loading…" : "More"}
                </Button>
              </li>
            ) : null}
          </ul>
        )}
      </div>

      {isFetchingNextPage && hasNextPage ? (
        <div className="sr-only" role="status">
          <Spinner size="sm" /> Loading more results
        </div>
      ) : null}
    </div>
  );
}
