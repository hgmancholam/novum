/**
 * useRun — single-run hook (BRD-13 / IP-13).
 *
 * Wraps `GET /api/runs/{id}` plus `cancel` / `fork` mutations. Event streaming
 * (SSE) is deferred to BRD-10; this hook intentionally does not subscribe to
 * any event endpoint.
 *
 * Per `eslint.config.js`, importers of `useRun*` are restricted to `pages/`.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";

import {
  cancelRun,
  forkRun,
  getRun,
  resumeRun,
  type RunResponseDto,
} from "@/lib/api";
import { ApiClientError } from "@/lib/api";
import { mapRun, type Run, type RunStatus, deriveStatus } from "@/types/run";

export interface UseRunResult {
  run: Run | undefined;
  status: RunStatus | undefined;
  isLoading: boolean;
  isError: boolean;
  /** True when the backend responded with 404 — used by `CenterPanelContainer` for C13. */
  isNotFound: boolean;
  error: Error | null;

  cancel: () => void;
  isCancelling: boolean;
  cancelError: Error | null;

  resume: () => void;
  isResuming: boolean;
  resumeError: Error | null;

  fork: (eventId: string) => void;
  isForking: boolean;
  forkError: Error | null;
  forkedRun: Run | undefined;
}

export const runQueryKey = (runId: string): readonly ["run", string] =>
  ["run", runId] as const;

export interface UseRunOptions {
  enabled?: boolean;
}

export function useRun(runId: string | undefined, options: UseRunOptions = {}): UseRunResult {
  const queryClient = useQueryClient();
  const enabled = (options.enabled ?? true) && typeof runId === "string" && runId.length > 0;

  const queryOptions: UseQueryOptions<RunResponseDto, Error, Run> = {
    queryKey: runId !== undefined ? runQueryKey(runId) : ["run", "__noop__"],
    queryFn: () => {
      if (runId === undefined) {
        throw new Error("runId is required");
      }
      return getRun(runId);
    },
    select: mapRun,
    enabled,
    staleTime: 5 * 1000,
  };

  const query = useQuery(queryOptions);

  const invalidate = (): void => {
    if (runId !== undefined) {
      void queryClient.invalidateQueries({ queryKey: runQueryKey(runId) });
    }
    void queryClient.invalidateQueries({ queryKey: ["runs"] });
  };

  const cancelMutation = useMutation<RunResponseDto, Error, void>({
    mutationFn: () => {
      if (runId === undefined) {
        throw new Error("runId is required");
      }
      return cancelRun(runId);
    },
    onSuccess: invalidate,
  });

  const resumeMutation = useMutation<RunResponseDto, Error, void>({
    mutationFn: () => {
      if (runId === undefined) {
        throw new Error("runId is required");
      }
      return resumeRun(runId);
    },
    onSuccess: invalidate,
  });

  const forkMutation = useMutation<RunResponseDto, Error, string>({
    mutationFn: (eventId: string) => {
      if (runId === undefined) {
        throw new Error("runId is required");
      }
      return forkRun(runId, eventId);
    },
    onSuccess: invalidate,
  });

  const status: RunStatus | undefined =
    query.data !== undefined
      ? deriveStatus({
          stop_reason: query.data.stopReason,
          stopped_at: query.data.stoppedAt,
        })
      : undefined;

  return {
    run: query.data,
    status,
    isLoading: query.isLoading,
    isError: query.isError,
    isNotFound:
      query.error instanceof ApiClientError && query.error.status === 404,
    error: query.error ?? null,

    cancel: () => {
      cancelMutation.mutate();
    },
    isCancelling: cancelMutation.isPending,
    cancelError: cancelMutation.error ?? null,

    resume: () => {
      resumeMutation.mutate();
    },
    isResuming: resumeMutation.isPending,
    resumeError: resumeMutation.error ?? null,

    fork: (eventId: string) => {
      forkMutation.mutate(eventId);
    },
    isForking: forkMutation.isPending,
    forkError: forkMutation.error ?? null,
    forkedRun: forkMutation.data !== undefined ? mapRun(forkMutation.data) : undefined,
  };
}
