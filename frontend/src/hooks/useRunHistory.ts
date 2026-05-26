/**
 * useRunHistory — paginated history hook (BRD-12, RF-09).
 *
 * Uses TanStack `useInfiniteQuery` over the backend's offset pagination.
 * Maps `RunListItemDto` → `RunSummary` with a derived `status`.
 */

import { useInfiniteQuery } from "@tanstack/react-query";

import { listRuns, type RunListItemDto } from "@/lib/api";
import type { RunStatus, RunSummary } from "@/types/history";

const PAGE_SIZE = 20;

export function mapRun(dto: RunListItemDto): RunSummary {
  let status: RunStatus;
  if (dto.stop_reason === null) {
    status = "running";
  } else if (dto.stop_reason === "judge_confirmed") {
    status = "completed";
  } else {
    status = "stopped";
  }
  return {
    id: dto.id,
    question: dto.question,
    status,
    stopReason: dto.stop_reason,
    startedAt: dto.started_at,
    stoppedAt: dto.stopped_at,
  };
}

export interface RunHistoryPage {
  items: RunSummary[];
  nextOffset: number | null;
}

export function useRunHistory(pageSize: number = PAGE_SIZE) {
  return useInfiniteQuery<RunHistoryPage>({
    queryKey: ["runs", "history", pageSize],
    initialPageParam: 0,
    queryFn: async ({ pageParam }) => {
      const offset = typeof pageParam === "number" ? pageParam : 0;
      const dtos = await listRuns({ limit: pageSize, offset });
      const items = dtos.map(mapRun);
      const nextOffset =
        items.length === pageSize ? offset + pageSize : null;
      return { items, nextOffset };
    },
    getNextPageParam: (lastPage) => lastPage.nextOffset ?? undefined,
    staleTime: 30 * 1000,
  });
}
