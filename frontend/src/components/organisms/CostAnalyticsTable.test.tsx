import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { CostAnalyticsTable } from "./CostAnalyticsTable";
import type { CostRow } from "@/types/costAnalytics";

const SAMPLE: CostRow[] = [
  {
    run_id: "run-a",
    owner: "alice",
    question: "Q1",
    occurred_at: "2026-05-01T10:00:00Z",
    provider: "anthropic",
    kind: "llm",
    model: "claude-sonnet",
    task_name: "planner",
    prompt_tokens: 100,
    completion_tokens: 50,
    cost_usd: 0.012,
  },
  {
    run_id: "run-b",
    owner: "bob",
    question: "Q2",
    occurred_at: "2026-05-02T10:00:00Z",
    provider: "openai",
    kind: "search",
    model: null,
    task_name: null,
    prompt_tokens: 0,
    completion_tokens: 0,
    cost_usd: 0.5,
  },
];

function renderTable(props: Partial<Parameters<typeof CostAnalyticsTable>[0]> = {}) {
  return render(
    <MemoryRouter>
      <CostAnalyticsTable rows={SAMPLE} {...props} />
    </MemoryRouter>
  );
}

describe("CostAnalyticsTable", () => {
  it("renders rows and a link per row", () => {
    renderTable();
    expect(screen.getAllByRole("link", { name: /open/i })).toHaveLength(2);
    expect(screen.getByText("claude-sonnet")).toBeInTheDocument();
  });

  it("shows empty state when rows is empty", () => {
    renderTable({ rows: [] });
    expect(screen.getByText(/no cost events/i)).toBeInTheDocument();
  });

  it("toggles sort direction when the same header is clicked twice", async () => {
    renderTable();
    const costHeader = screen.getByRole("button", { name: /^cost$/i });
    // First click on Cost (current sort is occurred_at desc) -> Cost desc
    await userEvent.click(costHeader);
    const header = costHeader.closest("th");
    expect(header).toHaveAttribute("aria-sort", "descending");
    await userEvent.click(costHeader);
    expect(header).toHaveAttribute("aria-sort", "ascending");
  });

  it("paginates when more rows than pageSize", () => {
    const many: CostRow[] = Array.from({ length: 60 }, (_, i) => ({
      ...SAMPLE[0]!,
      run_id: `r-${i}`,
      occurred_at: `2026-05-${String((i % 28) + 1).padStart(2, "0")}T10:00:00Z`,
    }));
    renderTable({ rows: many, pageSize: 25 });
    expect(screen.getByText(/page 1 \/ 3/i)).toBeInTheDocument();
  });

  it("renders correct count summary", () => {
    renderTable();
    const heading = screen.getByText("Cost events").parentElement!;
    expect(within(heading).getByText(/2 rows/i)).toBeInTheDocument();
  });
});
