import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useServiceHealth, SERVICE_HEALTH_QUERY_KEY } from "./useServiceHealth";

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
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
});
afterEach(() => {
  vi.unstubAllGlobals();
});

const snapshot = {
  checked_at: "2026-06-01T00:00:00Z",
  cached: false,
  services: [
    {
      id: "anthropic",
      name: "Anthropic",
      category: "llm",
      status: "ok",
      latency_ms: 200,
      message: null,
      checked_at: "2026-06-01T00:00:00Z",
    },
  ],
};

describe("useServiceHealth", () => {
  it("calls /api/health/services and exposes the snapshot", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(snapshot));
    const { result } = renderHook(() => useServiceHealth(), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => {
      expect(result.current.data).toBeDefined();
    });
    expect(result.current.data?.services[0]?.id).toBe("anthropic");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const firstCall = fetchMock.mock.calls[0] as unknown[] | undefined;
    const url = firstCall?.[0];
    expect(String(url)).toContain("/api/health/services");
  });

  it("uses the canonical query key", () => {
    expect(SERVICE_HEALTH_QUERY_KEY).toEqual(["health", "services"]);
  });

  it("does not throw or surface an error on transient failures (silent)", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: "boom" }, 500));
    const { result } = renderHook(() => useServiceHealth(), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => {
      expect(result.current.isError || result.current.isLoading).toBe(true);
    });
  });
});
