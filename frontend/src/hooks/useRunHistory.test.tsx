import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { mapRun, useRunHistory } from "./useRunHistory";
import type { RunListItemDto } from "@/lib/api";

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function dto(id: string, stop: RunListItemDto["stop_reason"] = null): RunListItemDto {
  return {
    id,
    question: `Q ${id}`,
    started_at: "2026-05-26T00:00:00Z",
    stopped_at: stop === null ? null : "2026-05-26T00:01:00Z",
    stop_reason: stop,
  };
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
      new Response(JSON.stringify([dto("a"), dto("b", "judge_confirmed")]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    const { result } = renderHook(() => useRunHistory(20), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    const items = result.current.data?.pages[0]?.items ?? [];
    expect(items).toHaveLength(2);
    expect(items[0]?.status).toBe("running");
    expect(items[1]?.status).toBe("completed");
    expect(result.current.hasNextPage).toBe(false);
  });

  it("flags hasNextPage when a full page is returned", async () => {
    const fullPage = Array.from({ length: 2 }, (_, i) => dto(`r${i.toString()}`));
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify(fullPage), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    const { result } = renderHook(() => useRunHistory(2), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.hasNextPage).toBe(true);
    expect(result.current.data?.pages[0]?.nextOffset).toBe(2);
  });

  it("surfaces fetch errors as isError", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ code: "X", message: "fail" }), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      })
    );
    const { result } = renderHook(() => useRunHistory(20), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
  });

  it("does not fetch when enabled is false", async () => {
    const { result } = renderHook(
      () => useRunHistory(20, { enabled: false }),
      { wrapper: makeWrapper() }
    );
    // Allow any pending microtasks to settle
    await new Promise((r) => setTimeout(r, 50));
    expect(fetchMock).not.toHaveBeenCalled();
    expect(result.current.data).toBeUndefined();
  });

  it("fetches when username changes (new queryKey triggers re-fetch)", async () => {
    const page = [dto("a")];
    // Use a factory so each call gets a fresh Response (body can only be read once)
    fetchMock.mockImplementation(() =>
      Promise.resolve(
        new Response(JSON.stringify(page), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
    );

    let username: string | null = "alice";
    const { result, rerender } = renderHook(
      () => useRunHistory(20, { enabled: true, username }),
      { wrapper: makeWrapper() }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // Simulate user switching: new username → new queryKey → new fetch
    username = "bob";
    rerender();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });
});
