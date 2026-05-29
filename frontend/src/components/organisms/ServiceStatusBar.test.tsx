import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { axe } from "jest-axe";

import { ServiceStatusBar } from "./ServiceStatusBar";
import type { HealthSnapshot } from "@/types/health";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.unstubAllGlobals();
});

const snapshot: HealthSnapshot = {
  checked_at: "2026-06-01T00:00:00Z",
  cached: false,
  services: [
    { id: "anthropic", name: "Anthropic", category: "llm", status: "ok", latency_ms: 200, message: null, checked_at: "2026-06-01T00:00:00Z" },
    { id: "openai", name: "OpenAI", category: "llm", status: "disabled", latency_ms: null, message: null, checked_at: "2026-06-01T00:00:00Z" },
    { id: "tavily", name: "Tavily", category: "search", status: "ok", latency_ms: 300, message: null, checked_at: "2026-06-01T00:00:00Z" },
    { id: "wikipedia", name: "Wikipedia", category: "knowledge", status: "degraded", latency_ms: 1700, message: null, checked_at: "2026-06-01T00:00:00Z" },
    { id: "postgres", name: "Postgres", category: "storage", status: "ok", latency_ms: 5, message: null, checked_at: "2026-06-01T00:00:00Z" },
  ],
};

describe("ServiceStatusBar", () => {
  it("renders the skeleton on first load", () => {
    fetchMock.mockImplementation(() => new Promise(() => undefined));
    render(<ServiceStatusBar />, { wrapper });
    expect(screen.getByTestId("service-status-bar-skeleton")).toBeInTheDocument();
  });

  it("renders a pill per service once data arrives", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(snapshot));
    render(<ServiceStatusBar />, { wrapper });
    await waitFor(() => {
      expect(screen.getAllByTestId("service-status-pill")).toHaveLength(5);
    });
    expect(screen.getByText("Anthropic")).toBeInTheDocument();
    expect(screen.getByText("Tavily")).toBeInTheDocument();
    expect(screen.getByText("Wikipedia")).toBeInTheDocument();
    expect(screen.getByText("Postgres")).toBeInTheDocument();
    expect(screen.getByText("OpenAI")).toBeInTheDocument();
  });

  it("groups pills in the canonical order llm → search → knowledge → storage", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(snapshot));
    render(<ServiceStatusBar />, { wrapper });
    await waitFor(() => {
      expect(screen.getAllByTestId("service-status-pill")).toHaveLength(5);
    });
    const pills = screen.getAllByTestId("service-status-pill");
    const ids = pills.map((p) => p.getAttribute("data-service-id"));
    // anthropic + openai (llm) come before tavily (search) before wikipedia (knowledge) before postgres (storage).
    expect(ids.indexOf("anthropic")).toBeLessThan(ids.indexOf("tavily"));
    expect(ids.indexOf("tavily")).toBeLessThan(ids.indexOf("wikipedia"));
    expect(ids.indexOf("wikipedia")).toBeLessThan(ids.indexOf("postgres"));
  });

  it("has an aria-label describing the footer for screen readers", () => {
    fetchMock.mockImplementation(() => new Promise(() => undefined));
    render(<ServiceStatusBar />, { wrapper });
    expect(screen.getByTestId("service-status-bar")).toHaveAttribute(
      "aria-label",
      "Service health",
    );
  });

  it("has no axe violations once populated", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(snapshot));
    const { container } = render(<ServiceStatusBar />, { wrapper });
    await waitFor(() => {
      expect(screen.getAllByTestId("service-status-pill")).toHaveLength(5);
    });
    expect(await axe(container)).toHaveNoViolations();
  });
});
