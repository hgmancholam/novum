/**
 * useCreateRun — create a new run (BRD-13 iter 2).
 *
 * Wraps POST /api/runs. Invalidates the history list on success and exposes
 * the created run via `data`. Caller is responsible for navigation.
 *
 * Per `eslint.config.js`, importers of `useRun*` are restricted to `pages/`.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  createRun,
  type RunCreatePayload,
  type RunResponseDto,
} from "@/lib/api";
import { mapRun, type Run } from "@/types/run";

export interface UseCreateRunResult {
  create: (payload: RunCreatePayload) => Promise<Run>;
  createdRun: Run | undefined;
  isPending: boolean;
  isError: boolean;
  error: Error | null;
  reset: () => void;
}

export function useCreateRun(): UseCreateRunResult {
  const queryClient = useQueryClient();

  const mutation = useMutation<RunResponseDto, Error, RunCreatePayload>({
    mutationFn: (payload) => createRun(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["runs"] });
    },
  });

  return {
    create: async (payload) => {
      const dto = await mutation.mutateAsync(payload);
      return mapRun(dto);
    },
    createdRun: mutation.data !== undefined ? mapRun(mutation.data) : undefined,
    isPending: mutation.isPending,
    isError: mutation.isError,
    error: mutation.error ?? null,
    reset: () => {
      mutation.reset();
    },
  };
}
