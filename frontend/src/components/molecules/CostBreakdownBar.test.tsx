import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { CostBreakdownBar } from "./CostBreakdownBar";
import type { ProviderCostRow } from "@/types/costs";

function row(partial: Partial<ProviderCostRow>): ProviderCostRow {
  return {
    provider: "anthropic",
    kind: "llm",
    model: null,
    calls: 1,
    prompt_tokens: 0,
    completion_tokens: 0,
    units: 0,
    cost_usd: 0,
    pct_of_total: 0,
    ...partial,
  };
}

describe("CostBreakdownBar", () => {
  it("renders one segment + legend entry per provider", () => {
    render(
      <CostBreakdownBar
        rows={[
          row({ provider: "anthropic", cost_usd: 0.05 }),
          row({ provider: "tavily", cost_usd: 0.02 }),
          row({ provider: "wikipedia", cost_usd: 0.01 }),
        ]}
      />
    );
    expect(screen.getByTestId("cost-bar-segment-anthropic")).toBeInTheDocument();
    expect(screen.getByTestId("cost-bar-segment-tavily")).toBeInTheDocument();
    expect(screen.getByTestId("cost-bar-segment-wikipedia")).toBeInTheDocument();
    expect(screen.getByText("anthropic")).toBeInTheDocument();
  });

  it("renders the empty state when there are no rows", () => {
    render(<CostBreakdownBar rows={[]} />);
    expect(screen.getByTestId("cost-breakdown-bar-empty")).toHaveTextContent(
      "No cost recorded yet."
    );
  });

  it("renders the empty state when total is zero", () => {
    render(
      <CostBreakdownBar
        rows={[row({ provider: "wikipedia", cost_usd: 0 })]}
      />
    );
    expect(screen.getByTestId("cost-breakdown-bar-empty")).toBeInTheDocument();
  });
});
