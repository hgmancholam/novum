/**
 * useRunHistory + useDeleteRun — history hooks (BRD-12, BRD-20, RF-09).
 *
 * `useRunHistory` wraps TanStack `useInfiniteQuery` over the backend's
 * cursor-based pagination (BRD-20 §4.4). `useDeleteRun` performs the
 * DELETE with optimistic removal across every cached history page
 * (BRD-20 AC-03, AC-10).
 */

import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
  type InfiniteData,
} from "@tanstack/react-query";

import { deleteRun, listRuns, type RunListItemDto } from "@/lib/api";
import { useSelectionStore } from "@/stores/selectionStore";
import { useToast } from "@/hooks/useToast";
import type {
  RunHistoryPage,
  RunStatus,
  RunSummary,
} from "@/types/history";

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
    username: dto.username,
    question: dto.question,
    status,
    stopReason: dto.stop_reason,
    startedAt: dto.started_at,
    stoppedAt: dto.stopped_at,
  };
}

export interface UseRunHistoryOptions {
  /** Only fetch when true (pass `isAuthenticated` from userStore). */
  enabled?: boolean;
  /** Include in queryKey so the cache resets on user change. */
  username?: string | null;
}

export function useRunHistory(
  pageSize: number = PAGE_SIZE,
  options: UseRunHistoryOptions = {}
) {
  const { enabled = true, username = null } = options;

  return useInfiniteQuery<RunHistoryPage>({
    queryKey: ["runs", "history", pageSize, username],
    enabled,
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const cursor =
        typeof pageParam === "string" && pageParam.length > 0
          ? pageParam
          : null;
      const dto = await listRuns({ limit: pageSize, cursor });
      return {
        items: dto.items.map(mapRun),
        hasMore: dto.has_more,
        nextCursor: dto.next_cursor,
      };
    },
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
    staleTime: 30 * 1000,
  });
}

/**
 * Optimistic delete with rollback (BRD-20 AC-03, AC-10).
 *
 * - ``onMutate`` snapshots every cached history page and removes the
 *   target id from each page's ``items``. The plural form
 *   ``getQueriesData`` / ``setQueriesData`` is REQUIRED because the
 *   query key includes ``pageSize`` and ``username`` — a single user
 *   may have multiple matching cache entries.
 * - ``onError`` restores the snapshot.
 * - ``onSuccess`` clears ``selectedRunId`` if the deleted row was
 *   selected (BRD-20 §4.6, RF-13 surface honesty).
 * - ``onError`` surfaces the literal microcopy from BRD-20 §14.3.
 * - ``onSettled`` invalidates the prefix so the next list reflects
 *   server truth (boundaries, has_more recompute).
 */
export function useDeleteRun() {
  const queryClient = useQueryClient();
  const toast = useToast();

  return useMutation<
    void,
    Error,
    string,
    { snapshots: Array<readonly [unknown, InfiniteData<RunHistoryPage> | undefined]> }
  >({
    mutationFn: async (runId: string) => {
      await deleteRun(runId);
    },
    onMutate: async (runId) => {
      await queryClient.cancelQueries({ queryKey: ["runs", "history"] });

      const snapshots = queryClient.getQueriesData<InfiniteData<RunHistoryPage>>({
        queryKey: ["runs", "history"],
      });

      queryClient.setQueriesData<InfiniteData<RunHistoryPage>>(
        { queryKey: ["runs", "history"] },
        (data) => {
          if (!data) return data;
          return {
            ...data,
            pages: data.pages.map((page) => ({
              ...page,
              items: page.items.filter((item) => item.id !== runId),
            })),
          };
        }
      );

      return { snapshots };
    },
    onError: (_err, _runId, context) => {
      if (context?.snapshots) {
        for (const [key, value] of context.snapshots) {
          queryClient.setQueryData(key as readonly unknown[], value);
        }
      }
      toast.push({
        kind: "error",
        message: "Couldn't delete the run. Please try again.",
      });
    },
    onSuccess: (_data, runId) => {
      const { selectedRunId, setSelectedRunId } = useSelectionStore.getState();
      if (selectedRunId === runId) {
        setSelectedRunId(null);
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["runs", "history"] });
    },
  });
}
