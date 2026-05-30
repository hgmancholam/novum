import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("recharts", async () => {
  const actual = await vi.importActual<typeof import("recharts")>("recharts");
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div style={{ width: 600, height: 300 }}>{children}</div>
    ),
  };
});

const fetchAnalytics = vi.fn();
vi.mock("@/lib/api/costAnalytics", () => ({
  fetchCostAnalytics: (...args: unknown[]): unknown => fetchAnalytics(...args),
}));

vi.mock("@/stores/userStore", () => ({
  useUserStore: (selector: (s: unknown) => unknown) =>
    selector({ isAuthenticated: true, isVerifying: false }),
}));

import CostAnalyticsPage from "./CostAnalyticsPage";
import type { CostAnalyticsResponse } from "@/types/costAnalytics";

const EMPTY: CostAnalyticsResponse = {
  date_from: "2026-04-01",
  date_to: "2026-05-01",
  totals: { cost_usd: 0, prompt_tokens: 0, completion_tokens: 0, calls: 0, runs: 0 },
  by_provider: [],
  by_kind: [],
  by_user: [],
  by_model: [],
  by_day: [],
  rows: [],
};

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/costs"]}>
        <CostAnalyticsPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("CostAnalyticsPage", () => {
  beforeEach(() => {
    fetchAnalytics.mockReset();
  });

  it("renders the dashboard when data loads", async () => {
    fetchAnalytics.mockResolvedValueOnce(EMPTY);
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("cost-dashboard")).toBeInTheDocument();
    });
    expect(screen.getByText("Cost analytics")).toBeInTheDocument();
  });

  it("renders an error state on failure", async () => {
    fetchAnalytics.mockRejectedValueOnce(new Error("boom"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("analytics-error")).toBeInTheDocument();
    });
    expect(screen.getByText(/boom/)).toBeInTheDocument();
  });
});
