import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { axe } from "jest-axe";

import { HistoryList, type HistoryListProps } from "./HistoryList";
import type { RunSummary } from "@/types/history";

const sampleRuns: RunSummary[] = [
  {
    id: "r1",
    username: "alice",
    question: "Capital of France?",
    status: "completed",
    stopReason: "judge_confirmed",
    startedAt: new Date(Date.now() - 60_000).toISOString(),
    stoppedAt: null,
  },
  {
    id: "r2",
    username: "bob",
    question: "Population of Tokyo?",
    status: "running",
    stopReason: null,
    startedAt: new Date(Date.now() - 120_000).toISOString(),
    stoppedAt: null,
  },
  {
    id: "r3",
    username: "alice",
    question: "Tallest mountain?",
    status: "stopped",
    stopReason: "honest_unanswerable",
    startedAt: new Date(Date.now() - 180_000).toISOString(),
    stoppedAt: null,
  },
];

function setup(overrides: Partial<HistoryListProps> = {}): HistoryListProps {
  return {
    runs: sampleRuns,
    selectedRunId: null,
    filters: {},
    onFiltersChange: vi.fn(),
    onSelectRun: vi.fn(),
    onNewQuestion: vi.fn(),
    isLoading: false,
    isError: false,
    onRetry: vi.fn(),
    hasNextPage: false,
    isFetchingNextPage: false,
    onLoadMore: vi.fn(),
    ...overrides,
  };
}

describe("HistoryList", () => {
  it("L1 — shows empty state with a CTA when no runs", () => {
    const props = setup({ runs: [] });
    render(<HistoryList {...props} />);
    expect(screen.getByText("No research runs yet.")).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Start your first research" })
    );
    expect(props.onNewQuestion).toHaveBeenCalledTimes(1);
  });

  it("L2 — renders one RunRow per run", () => {
    render(<HistoryList {...setup()} />);
    expect(screen.getAllByTestId("run-row")).toHaveLength(3);
  });

  it("L3 — marks the selected run", () => {
    render(<HistoryList {...setup({ selectedRunId: "r2" })} />);
    const rows = screen.getAllByTestId("run-row");
    const selected = rows.filter(
      (r) => r.getAttribute("data-selected") === "true"
    );
    expect(selected).toHaveLength(1);
    expect(selected[0]?.textContent ?? "").toContain("Population of Tokyo?");
  });

  it("L5 — shows skeletons while loading", () => {
    render(<HistoryList {...setup({ isLoading: true, runs: [] })} />);
    expect(screen.getAllByTestId("run-row-skeleton").length).toBeGreaterThan(0);
  });

  it("L6 — shows error and triggers retry", () => {
    const props = setup({
      isError: true,
      errorMessage: "boom",
      runs: [],
    });
    render(<HistoryList {...props} />);
    expect(screen.getByText("boom")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(props.onRetry).toHaveBeenCalledTimes(1);
  });

  it("L7 — filters by status client-side", () => {
    render(<HistoryList {...setup({ filters: { status: "running" } })} />);
    const rows = screen.getAllByTestId("run-row");
    expect(rows).toHaveLength(1);
    expect(rows[0]?.textContent ?? "").toContain("Population of Tokyo?");
  });

  it("L7 — filters by search client-side, shows specific empty CTA", () => {
    render(
      <HistoryList {...setup({ filters: { search: "nothing-matches" } })} />
    );
    expect(screen.getByText("No runs match your filters.")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "New question" })
    ).toBeInTheDocument();
  });

  it("AC-04 — load more button calls onLoadMore", () => {
    const props = setup({ hasNextPage: true });
    render(<HistoryList {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Load more" }));
    expect(props.onLoadMore).toHaveBeenCalledTimes(1);
  });

  it("forwards selection clicks to onSelectRun", () => {
    const props = setup();
    render(<HistoryList {...props} />);
    fireEvent.click(screen.getAllByTestId("run-row")[0] as HTMLElement);
    expect(props.onSelectRun).toHaveBeenCalledWith("r1");
  });

  it("has no a11y violations in the populated state", async () => {
    const { container } = render(<HistoryList {...setup()} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
