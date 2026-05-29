import { describe, expect, it } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { axe } from "jest-axe";

import { CostBreakdownTable } from "./CostBreakdownTable";
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
  {
    provider: "tavily",
    kind: "search",
    model: null,
    calls: 4,
    prompt_tokens: 0,
    completion_tokens: 0,
    units: 8,
    cost_usd: 0.0368,
    pct_of_total: 37.5,
  },
  {
    provider: "wikipedia",
    kind: "search",
    model: null,
    calls: 3,
    prompt_tokens: 0,
    completion_tokens: 0,
    units: 3,
    cost_usd: 0,
    pct_of_total: 0,
  },
];

describe("CostBreakdownTable", () => {
  it("renders an em-dash for free rows", () => {
    render(<CostBreakdownTable rows={ROWS} />);
    const table = screen.getByTestId("cost-breakdown-table");
    const wikipediaRow = within(table).getByText("wikipedia").closest("tr");
    expect(wikipediaRow).not.toBeNull();
    expect(
      within(wikipediaRow as HTMLElement).getAllByText("—").length
    ).toBeGreaterThan(0);
  });

  it("renders an em-dash when model is null", () => {
    render(<CostBreakdownTable rows={ROWS} />);
    const tavilyRow = screen.getByText("tavily").closest("tr");
    expect(tavilyRow).not.toBeNull();
    expect(
      within(tavilyRow as HTMLElement).getAllByText("—").length
    ).toBeGreaterThan(0);
  });

  it("toggles sort direction when the active header is clicked again", () => {
    render(<CostBreakdownTable rows={ROWS} />);
    const usdHeader = screen.getByRole("button", { name: /USD/ });
    fireEvent.click(usdHeader);
    fireEvent.click(usdHeader);
    expect(screen.getByTestId("cost-breakdown-table")).toBeInTheDocument();
  });

  it("renders an empty body when rows are empty", () => {
    render(<CostBreakdownTable rows={[]} />);
    expect(screen.getByText("No cost rows.")).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<CostBreakdownTable rows={ROWS} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
