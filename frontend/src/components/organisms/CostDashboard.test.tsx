import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("recharts", async () => {
  const actual = await vi.importActual<typeof import("recharts")>("recharts");
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div style={{ width: 600, height: 300 }}>{children}</div>
    ),
  };
});

import { CostDashboard } from "./CostDashboard";
import type { CostAnalyticsResponse } from "@/types/costAnalytics";

const SAMPLE: CostAnalyticsResponse = {
  date_from: "2026-04-01",
  date_to: "2026-05-01",
  totals: {
    cost_usd: 12.34,
    prompt_tokens: 5000,
    completion_tokens: 2500,
    calls: 42,
    runs: 7,
  },
  by_provider: [
    { provider: "anthropic", cost_usd: 10, calls: 30, tokens: 6000, pct_of_total: 81 },
    { provider: "openai", cost_usd: 2.34, calls: 12, tokens: 1500, pct_of_total: 19 },
  ],
  by_kind: [
    { kind: "llm", cost_usd: 11.5, calls: 35, tokens: 7000 },
    { kind: "search", cost_usd: 0.84, calls: 7, tokens: 500 },
  ],
  by_model: [
    { provider: "anthropic", model: "claude-sonnet", cost_usd: 10, calls: 30, tokens: 6000 },
  ],
  by_day: [
    { date: "2026-04-30", cost_usd: 5, calls: 10, tokens: 1000 },
    { date: "2026-05-01", cost_usd: 7.34, calls: 32, tokens: 6500 },
  ],
  rows: [],
};

describe("CostDashboard", () => {
  it("renders the four KPI cards", () => {
    render(<CostDashboard data={SAMPLE} />);
    expect(screen.getByTestId("kpi-total-cost")).toBeInTheDocument();
    expect(screen.getByTestId("kpi-total-tokens")).toBeInTheDocument();
    expect(screen.getByTestId("kpi-runs")).toBeInTheDocument();
    expect(screen.getByTestId("kpi-avg-per-run")).toBeInTheDocument();
  });

  it("formats the total cost", () => {
    render(<CostDashboard data={SAMPLE} />);
    expect(screen.getAllByText("$12.34").length).toBeGreaterThan(0);
  });

  it("renders all four charts", () => {
    render(<CostDashboard data={SAMPLE} />);
    expect(screen.getByTestId("cost-line-chart")).toBeInTheDocument();
    expect(screen.getByTestId("cost-donut")).toBeInTheDocument();
    expect(screen.getByTestId("kind-bar-chart")).toBeInTheDocument();
    expect(screen.getByTestId("top-models-chart")).toBeInTheDocument();
  });
});
