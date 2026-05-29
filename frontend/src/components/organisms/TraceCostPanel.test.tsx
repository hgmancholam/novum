import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { TraceCostPanel } from "./TraceCostPanel";
import type { ProviderCostRow } from "@/types/costs";

const ROWS: ProviderCostRow[] = [
  {
    provider: "anthropic",
    kind: "llm",
    model: "claude-sonnet-4-5",
    calls: 7,
    prompt_tokens: 4_300,
    completion_tokens: 1_200,
    units: 0,
    cost_usd: 0.0612,
    pct_of_total: 62.4,
  },
];

describe("TraceCostPanel", () => {
  it("renders a loading skeleton", () => {
    render(
      <TraceCostPanel
        totalUsd={0}
        totalPromptTokens={0}
        totalCompletionTokens={0}
        rows={[]}
        isLoading
      />
    );
    expect(screen.getByTestId("trace-cost-panel-loading")).toBeInTheDocument();
  });

  it("renders an error state with a retry button", () => {
    const retry = vi.fn();
    render(
      <TraceCostPanel
        totalUsd={0}
        totalPromptTokens={0}
        totalCompletionTokens={0}
        rows={[]}
        isError
        onRetry={retry}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: /Retry/ }));
    expect(retry).toHaveBeenCalledTimes(1);
  });

  it("renders the header total and the breakdown", () => {
    render(
      <TraceCostPanel
        totalUsd={0.0612}
        totalPromptTokens={4_300}
        totalCompletionTokens={1_200}
        rows={ROWS}
      />
    );
    expect(screen.getByText("Cost breakdown")).toBeInTheDocument();
    expect(screen.getByTestId("cost-breakdown-table")).toBeInTheDocument();
    expect(screen.getAllByText("$0.0612").length).toBeGreaterThan(0);
  });
});
