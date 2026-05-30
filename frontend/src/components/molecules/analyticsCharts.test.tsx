import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

// Avoid ResponsiveContainer's 0x0 measurement issue in jsdom.
vi.mock("recharts", async () => {
  const actual = await vi.importActual<typeof import("recharts")>("recharts");
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div style={{ width: 600, height: 300 }}>{children}</div>
    ),
  };
});

import { CostLineChart } from "./CostLineChart";
import { CostDonut } from "./CostDonut";
import { KindBarChart } from "./KindBarChart";
import { TopModelsChart } from "./TopModelsChart";

describe("analytics charts", () => {
  it("CostLineChart renders title and empty state", () => {
    render(<CostLineChart data={[]} />);
    expect(screen.getByText("Daily cost & tokens")).toBeInTheDocument();
    expect(screen.getByText(/no data/i)).toBeInTheDocument();
  });

  it("CostLineChart renders chart container when data is present", () => {
    render(
      <CostLineChart
        data={[{ date: "2026-05-01", cost_usd: 1.5, calls: 3, tokens: 1234 }]}
      />
    );
    expect(screen.getByTestId("cost-line-chart")).toBeInTheDocument();
  });

  it("CostDonut renders empty state when total is zero", () => {
    render(<CostDonut data={[]} />);
    expect(screen.getByText("Cost by provider")).toBeInTheDocument();
    expect(screen.getByText(/no cost/i)).toBeInTheDocument();
  });

  it("CostDonut renders with data", () => {
    render(
      <CostDonut
        data={[
          {
            provider: "anthropic",
            cost_usd: 1,
            calls: 1,
            tokens: 100,
            pct_of_total: 100,
          },
        ]}
      />
    );
    expect(screen.getByTestId("cost-donut")).toBeInTheDocument();
  });

  it("KindBarChart renders title", () => {
    render(<KindBarChart data={[]} />);
    expect(screen.getByText("Cost by kind")).toBeInTheDocument();
  });

  it("TopModelsChart renders empty state", () => {
    render(<TopModelsChart data={[]} />);
    expect(screen.getByText("Top models by cost")).toBeInTheDocument();
    expect(screen.getByText(/no model data/i)).toBeInTheDocument();
  });
});
