/**
 * Connected history panel for pages.
 * Owns `useRunHistory` and local filter state, then renders the
 * presentational `HistoryList` inside the `templates/HistoryPanel` shell.
 *
 * Lives under `pages/` so the ESLint `import/no-restricted-paths` rule
 * (no `useRun*` outside `pages/`) is respected.
 */

import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/atoms";
import { HistoryList } from "@/components/organisms/HistoryList";
import { HistoryPanel } from "@/components/templates";
import { useDeleteRun, useRunHistory } from "@/hooks/useRunHistory";
import { useSelectionStore } from "@/stores/selectionStore";
import { useUserStore } from "@/stores/userStore";
import type { HistoryFilterValues, RunSummary } from "@/types/history";

export function HistoryPanelContainer() {
  const navigate = useNavigate();
  const selectedRunId = useSelectionStore((s) => s.selectedRunId);
  const setSelectedRunId = useSelectionStore((s) => s.setSelectedRunId);

  const isAuthenticated = useUserStore((s) => s.isAuthenticated);
  const username = useUserStore((s) => s.user?.username ?? null);

  const [filters, setFilters] = useState<HistoryFilterValues>({});
  const [isManualRefreshing, setIsManualRefreshing] = useState(false);

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useRunHistory(undefined, { enabled: isAuthenticated, username });

  const runs: RunSummary[] =
    data?.pages.flatMap((page) => page.items) ?? [];

  const handleSelect = useCallback(
    (runId: string): void => {
      setSelectedRunId(runId);
      void navigate(`/runs/${runId}`);
    },
    [navigate, setSelectedRunId]
  );

  const handleNewQuestion = useCallback((): void => {
    void navigate("/run");
  }, [navigate]);

  const handleRetry = useCallback((): void => {
    setIsManualRefreshing(true);
    void refetch().finally(() => { setIsManualRefreshing(false); });
  }, [refetch]);

  const handleLoadMore = useCallback((): void => {
    void fetchNextPage();
  }, [fetchNextPage]);

  const deleteMutation = useDeleteRun();
  const handleDelete = useCallback(
    (runId: string): void => {
      deleteMutation.mutate(runId);
    },
    [deleteMutation]
  );

  return (
    <HistoryPanel
      header={
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium text-[var(--text-primary)]">
            History
          </h2>
          <Button size="sm" onClick={handleNewQuestion}>
            New
          </Button>
        </div>
      }
      body={
        <HistoryList
          runs={runs}
          selectedRunId={selectedRunId}
          filters={filters}
          onFiltersChange={setFilters}
          onSelectRun={handleSelect}
          onNewQuestion={handleNewQuestion}
          onDeleteRun={handleDelete}
          isLoading={isLoading}
          isError={isError}
          {...(error instanceof Error ? { errorMessage: error.message } : {})}
          onRetry={handleRetry}
          onRefresh={handleRetry}
          isRefreshing={isManualRefreshing}
          hasNextPage={hasNextPage}
          isFetchingNextPage={isFetchingNextPage}
          onLoadMore={handleLoadMore}
        />
      }
    />
  );
}
