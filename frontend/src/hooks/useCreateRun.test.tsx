import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useCreateRun } from "./useCreateRun";

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
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
  localStorage.setItem("novum_username", "alice");
  localStorage.setItem("novum_token", "secret-token");
});
afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("useCreateRun", () => {
  it("POSTs to /api/runs with auth headers and returns a mapped Run", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        id: "11111111-1111-1111-1111-111111111111",
        owner_username: "alice",
        question: "What is event sourcing?",
        user_context: null,
        question_type: null,
        output_format: "structured",
        confidence_threshold: 0.6,
        started_at: "2026-05-26T00:00:00Z",
        stopped_at: null,
        stop_reason: null,
        parent_run_id: null,
        forked_at_event_id: null,
      })
    );

    const { result } = renderHook(() => useCreateRun(), {
      wrapper: makeWrapper(),
    });

    const run = await result.current.create({
      question: "What is event sourcing?",
    });

    expect(run.id).toBe("11111111-1111-1111-1111-111111111111");
    expect(run.ownerUsername).toBe("alice");

    const call = fetchMock.mock.calls[0];
    expect(call).toBeDefined();
    const [url, init] = call as [string, RequestInit];
    expect(url).toContain("/api/runs");
    expect(init.method).toBe("POST");
    const headers = init.headers as Record<string, string>;
    expect(headers["X-Username"]).toBe("alice");
    expect(headers["X-Token"]).toBe("secret-token");
    expect(headers["Content-Type"]).toBe("application/json");

    await waitFor(() => {
      expect(result.current.createdRun?.id).toBe(
        "11111111-1111-1111-1111-111111111111"
      );
    });
  });

  it("exposes the error on failure", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ code: "VALIDATION", message: "too short" }, 422)
    );
    const { result } = renderHook(() => useCreateRun(), {
      wrapper: makeWrapper(),
    });
    await expect(result.current.create({ question: "x" })).rejects.toThrow();
    await waitFor(() => {
      expect(result.current.error).not.toBeNull();
    });
  });
});
