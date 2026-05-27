import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider, type InfiniteData } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { mapRun, useDeleteRun, useRunHistory } from "./useRunHistory";
import type { RunListItemDto, RunListPageDto } from "@/lib/api";
import { useSelectionStore } from "@/stores/selectionStore";
import { useToastStore } from "@/stores/toastStore";
import type { RunHistoryPage } from "@/types/history";

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { client, Wrapper };
}

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  useSelectionStore.getState().reset();
  useToastStore.getState().reset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function dto(id: string, stop: RunListItemDto["stop_reason"] = null): RunListItemDto {
  return {
    id,
    username: "testuser",
    question: `Q ${id}`,
    started_at: "2026-05-26T00:00:00Z",
    stopped_at: stop === null ? null : "2026-05-26T00:01:00Z",
    stop_reason: stop,
  };
}

function pageDto(
  items: RunListItemDto[],
  nextCursor: string | null = null
): RunListPageDto {
  return { items, has_more: nextCursor !== null, next_cursor: nextCursor };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("mapRun", () => {
  it("maps stop_reason=null to running", () => {
    expect(mapRun(dto("a"))).toMatchObject({ status: "running" });
  });
  it("maps judge_confirmed to completed", () => {
    expect(mapRun(dto("a", "judge_confirmed"))).toMatchObject({
      status: "completed",
    });
  });
  it("maps other stops to stopped", () => {
    expect(mapRun(dto("a", "honest_unanswerable"))).toMatchObject({
      status: "stopped",
    });
    expect(mapRun(dto("a", "user_cancelled"))).toMatchObject({
      status: "stopped",
    });
    expect(mapRun(dto("a", "errored"))).toMatchObject({ status: "stopped" });
  });
});

describe("useRunHistory", () => {
  it("fetches the first page and exposes mapped runs", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(pageDto([dto("a"), dto("b", "judge_confirmed")]))
    );

    const { Wrapper } = makeWrapper();
    const { result } = renderHook(() => useRunHistory(20), { wrapper: Wrapper });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    const items = result.current.data?.pages[0]?.items ?? [];
    expect(items).toHaveLength(2);
    expect(items[0]?.status).toBe("running");
    expect(items[1]?.status).toBe("completed");
    expect(result.current.hasNextPage).toBe(false);
  });

  it("flags hasNextPage when the page carries a next_cursor", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(pageDto([dto("a"), dto("b")], "cur-1"))
    );

    const { Wrapper } = makeWrapper();
    const { result } = renderHook(() => useRunHistory(2), { wrapper: Wrapper });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.hasNextPage).toBe(true);
    expect(result.current.data?.pages[0]?.nextCursor).toBe("cur-1");
  });

  it("passes the cursor through on fetchNextPage", async () => {
    fetchMock.mockImplementation((url: unknown) => {
      const str = String(url);
      if (str.includes("cursor=cur-XYZ")) {
        return Promise.resolve(jsonResponse(pageDto([dto("b")])));
      }
      return Promise.resolve(jsonResponse(pageDto([dto("a")], "cur-XYZ")));
    });

    const { Wrapper } = makeWrapper();
    const { result } = renderHook(() => useRunHistory(1), { wrapper: Wrapper });

    await waitFor(() => {
      expect(result.current.hasNextPage).toBe(true);
    });

    await act(async () => {
      void result.current.fetchNextPage();
    });

    await waitFor(() => {
      expect(result.current.isFetchingNextPage).toBe(false);
      expect(result.current.data?.pages.length).toBe(2);
    });

    const cursoredCall = fetchMock.mock.calls.find((args) =>
      String(args[0]).includes("cursor=cur-XYZ")
    );
    expect(cursoredCall).toBeDefined();
  });

  it("surfaces fetch errors as isError", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ code: "X", message: "fail" }, 500)
    );
    const { Wrapper } = makeWrapper();
    const { result } = renderHook(() => useRunHistory(20), { wrapper: Wrapper });
    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
  });

  it("does not fetch when enabled is false", async () => {
    const { Wrapper } = makeWrapper();
    const { result } = renderHook(
      () => useRunHistory(20, { enabled: false }),
      { wrapper: Wrapper }
    );
    await new Promise((r) => setTimeout(r, 50));
    expect(fetchMock).not.toHaveBeenCalled();
    expect(result.current.data).toBeUndefined();
  });

  it("fetches when username changes (new queryKey triggers re-fetch)", async () => {
    fetchMock.mockImplementation(() =>
      Promise.resolve(jsonResponse(pageDto([dto("a")])))
    );

    let username: string | null = "alice";
    const { Wrapper } = makeWrapper();
    const { result, rerender } = renderHook(
      () => useRunHistory(20, { enabled: true, username }),
      { wrapper: Wrapper }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetchMock).toHaveBeenCalledTimes(1);

    username = "bob";
    rerender();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });
});

describe("useDeleteRun", () => {
  function mockHappyPath(): void {
    let deleted = false;
    fetchMock.mockImplementation((_url: unknown, init?: RequestInit) => {
      const method = (init?.method ?? "GET").toUpperCase();
      if (method === "DELETE") {
        deleted = true;
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      const items = deleted ? [dto("b")] : [dto("a"), dto("b")];
      return Promise.resolve(jsonResponse(pageDto(items)));
    });
  }

  it("optimistically removes the row across cached pages", async () => {
    mockHappyPath();

    const { client, Wrapper } = makeWrapper();
    const { result } = renderHook(
      () => ({ history: useRunHistory(20), del: useDeleteRun() }),
      { wrapper: Wrapper }
    );
    await waitFor(() => expect(result.current.history.isSuccess).toBe(true));

    await act(async () => {
      await result.current.del.mutateAsync("a");
    });

    await waitFor(() => {
      const cached = client.getQueriesData<InfiniteData<RunHistoryPage>>({
        queryKey: ["runs", "history"],
      });
      const allItems = cached.flatMap(
        ([, data]) => data?.pages.flatMap((p) => p.items) ?? []
      );
      expect(allItems.find((r) => r.id === "a")).toBeUndefined();
    });
  });

  it("rolls back the cache and pushes an error toast on failure", async () => {
    fetchMock.mockImplementation((_url: unknown, init?: RequestInit) => {
      const method = (init?.method ?? "GET").toUpperCase();
      if (method === "DELETE") {
        return Promise.resolve(
          jsonResponse({ code: "X", message: "boom" }, 500)
        );
      }
      return Promise.resolve(jsonResponse(pageDto([dto("a"), dto("b")])));
    });

    const { Wrapper } = makeWrapper();
    const { result: history } = renderHook(() => useRunHistory(20), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(history.current.isSuccess).toBe(true));

    const { result: del } = renderHook(() => useDeleteRun(), { wrapper: Wrapper });
    await act(async () => {
      try {
        await del.current.mutateAsync("a");
      } catch {
        /* expected */
      }
    });

    await waitFor(() => {
      const items = history.current.data?.pages[0]?.items ?? [];
      expect(items.find((r) => r.id === "a")).toBeDefined();
    });

    const toasts = useToastStore.getState().toasts;
    expect(toasts).toHaveLength(1);
    expect(toasts[0]?.message).toBe(
      "Couldn't delete the run. Please try again."
    );
    expect(toasts[0]?.kind).toBe("error");
  });

  it("clears selectedRunId when the deleted run was selected", async () => {
    mockHappyPath();
    useSelectionStore.getState().setSelectedRunId("a");

    const { Wrapper } = makeWrapper();
    const { result: history } = renderHook(() => useRunHistory(20), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(history.current.isSuccess).toBe(true));

    const { result: del } = renderHook(() => useDeleteRun(), { wrapper: Wrapper });
    await act(async () => {
      await del.current.mutateAsync("a");
    });

    expect(useSelectionStore.getState().selectedRunId).toBeNull();
  });

  it("does not clear selectedRunId when a different run is deleted", async () => {
    mockHappyPath();
    useSelectionStore.getState().setSelectedRunId("b");

    const { Wrapper } = makeWrapper();
    const { result: history } = renderHook(() => useRunHistory(20), {
      wrapper: Wrapper,
    });
    await waitFor(() => expect(history.current.isSuccess).toBe(true));

    const { result: del } = renderHook(() => useDeleteRun(), { wrapper: Wrapper });
    await act(async () => {
      await del.current.mutateAsync("a");
    });

    expect(useSelectionStore.getState().selectedRunId).toBe("b");
  });
});
