import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useRun } from "./useRun";
import type { RunResponseDto } from "@/lib/api";

function makeWrapper(client = new QueryClient({
  defaultOptions: { queries: { retry: false } },
})) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

const RUN_ID = "00000000-0000-0000-0000-000000000001";

function makeDto(overrides: Partial<RunResponseDto> = {}): RunResponseDto {
  return {
    id: RUN_ID,
    owner_username: "alice",
    question: "Is water wet?",
    user_context: null,
    question_type: "factual",
    output_format: "prose",
    confidence_threshold: 0.7,
    started_at: "2026-05-26T00:00:00Z",
    stopped_at: null,
    stop_reason: null,
    parent_run_id: null,
    forked_at_event_id: null,
    ...overrides,
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  localStorage.setItem("novum_username", "alice");
  localStorage.setItem("novum_token", "secret-token");
});

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("useRun", () => {
  it("returns the mapped Run and derived status on success (running)", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(makeDto()));

    const { result } = renderHook(() => useRun(RUN_ID), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => {
      expect(result.current.run).toBeDefined();
    });

    expect(result.current.run?.id).toBe(RUN_ID);
    expect(result.current.run?.ownerUsername).toBe("alice");
    expect(result.current.run?.confidenceThreshold).toBe(0.7);
    expect(result.current.status).toBe("running");
    expect(result.current.isError).toBe(false);
  });

  it("derives status='stopped' when the dto has a stop_reason", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        makeDto({
          stop_reason: "judge_confirmed",
          stopped_at: "2026-05-26T00:01:00Z",
        })
      )
    );
    const { result } = renderHook(() => useRun(RUN_ID), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => {
      expect(result.current.status).toBe("stopped");
    });
    expect(result.current.run?.stopReason).toBe("judge_confirmed");
  });

  it("surfaces fetch errors via isError", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ code: "NOT_FOUND", message: "missing" }, 404)
    );
    const { result } = renderHook(() => useRun(RUN_ID), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
    expect(result.current.run).toBeUndefined();
    expect(result.current.error).not.toBeNull();
  });

  it("starts in loading state", () => {
    fetchMock.mockImplementation(
      () => new Promise<Response>(() => {
        // never resolves
      })
    );
    const { result } = renderHook(() => useRun(RUN_ID), {
      wrapper: makeWrapper(),
    });
    expect(result.current.isLoading).toBe(true);
    expect(result.current.run).toBeUndefined();
  });

  it("is disabled when runId is undefined", () => {
    const { result } = renderHook(() => useRun(undefined), {
      wrapper: makeWrapper(),
    });
    expect(result.current.isLoading).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("cancel() POSTs with auth headers and invalidates the query", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(makeDto())); // initial GET
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        makeDto({
          stop_reason: "user_cancelled",
          stopped_at: "2026-05-26T00:02:00Z",
        })
      )
    ); // POST /cancel
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        makeDto({
          stop_reason: "user_cancelled",
          stopped_at: "2026-05-26T00:02:00Z",
        })
      )
    ); // refetch after invalidation

    const { result } = renderHook(() => useRun(RUN_ID), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => {
      expect(result.current.status).toBe("running");
    });

    act(() => {
      result.current.cancel();
    });

    await waitFor(() => {
      expect(result.current.status).toBe("stopped");
    });

    const cancelCall = fetchMock.mock.calls.find(
      (call: unknown[]) => {
        const url = call[0];
        return typeof url === "string" && url.endsWith(`/api/runs/${RUN_ID}/cancel`);
      }
    );
    expect(cancelCall).toBeDefined();
    const init = cancelCall?.[1] as RequestInit | undefined;
    expect(init?.method).toBe("POST");
    const headers = init?.headers as Record<string, string>;
    expect(headers["X-Username"]).toBe("alice");
    expect(headers["X-Token"]).toBe("secret-token");
  });

  it("fork() POSTs with the event_id body", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(makeDto())); // initial GET
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        makeDto({
          id: "00000000-0000-0000-0000-000000000999",
          parent_run_id: RUN_ID,
          forked_at_event_id: "11111111-1111-1111-1111-111111111111",
        })
      )
    ); // POST /fork
    fetchMock.mockResolvedValue(jsonResponse(makeDto())); // any refetch

    const { result } = renderHook(() => useRun(RUN_ID), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => {
      expect(result.current.run).toBeDefined();
    });

    act(() => {
      result.current.fork("11111111-1111-1111-1111-111111111111");
    });

    await waitFor(() => {
      expect(result.current.forkedRun?.parentRunId).toBe(RUN_ID);
    });

    const forkCall = fetchMock.mock.calls.find(
      (call: unknown[]) => {
        const url = call[0];
        return typeof url === "string" && url.endsWith(`/api/runs/${RUN_ID}/fork`);
      }
    );
    expect(forkCall).toBeDefined();
    const init = forkCall?.[1] as RequestInit | undefined;
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toEqual({
      event_id: "11111111-1111-1111-1111-111111111111",
    });
  });
});
