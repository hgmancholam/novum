import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { axe } from "jest-axe";

import { HistoryItem } from "./HistoryItem";
import type { RunSummary } from "@/types/history";

function run(overrides: Partial<RunSummary> = {}): RunSummary {
  return {
    id: "r1",
    username: "alice",
    question: "Question?",
    status: "completed",
    stopReason: "judge_confirmed",
    startedAt: new Date(Date.now() - 60_000).toISOString(),
    stoppedAt: null,
    ...overrides,
  };
}

describe("HistoryItem", () => {
  it("renders the underlying RunRow and a delete affordance for finished runs", () => {
    render(
      <HistoryItem
        run={run()}
        isSelected={false}
        onSelect={vi.fn()}
        onDelete={vi.fn()}
      />
    );
    expect(screen.getByTestId("run-row")).toBeInTheDocument();
    expect(screen.getByTestId("history-item-delete")).toBeInTheDocument();
  });

  it("BRD-20 §14.3 — uses the exact 'Delete run' microcopy", () => {
    render(
      <HistoryItem
        run={run()}
        isSelected={false}
        onSelect={vi.fn()}
        onDelete={vi.fn()}
      />
    );
    const button = screen.getByTestId("history-item-delete");
    expect(button).toHaveAttribute("aria-label", "Delete run");
    expect(button).toHaveAttribute("title", "Delete run");
  });

  it("BRD-20 §4.6 — hides the delete affordance for running runs", () => {
    render(
      <HistoryItem
        run={run({ status: "running", stopReason: null })}
        isSelected={false}
        onSelect={vi.fn()}
        onDelete={vi.fn()}
      />
    );
    expect(screen.queryByTestId("history-item-delete")).toBeNull();
  });

  it("hides the delete affordance when no onDelete callback is supplied", () => {
    render(<HistoryItem run={run()} isSelected={false} onSelect={vi.fn()} />);
    expect(screen.queryByTestId("history-item-delete")).toBeNull();
  });

  it("BRD-20 AC-15 — calls onDelete and stops propagation to the row", () => {
    const onSelect = vi.fn();
    const onDelete = vi.fn();
    render(
      <HistoryItem
        run={run()}
        isSelected={false}
        onSelect={onSelect}
        onDelete={onDelete}
      />
    );
    fireEvent.click(screen.getByTestId("history-item-delete"));
    expect(onDelete).toHaveBeenCalledWith("r1");
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("forwards row clicks to onSelect", () => {
    const onSelect = vi.fn();
    render(
      <HistoryItem
        run={run()}
        isSelected={false}
        onSelect={onSelect}
        onDelete={vi.fn()}
      />
    );
    fireEvent.click(screen.getByTestId("run-row"));
    expect(onSelect).toHaveBeenCalledWith("r1");
  });

  it("has no a11y violations", async () => {
    const { container } = render(
      <ul>
        <HistoryItem
          run={run()}
          isSelected={false}
          onSelect={vi.fn()}
          onDelete={vi.fn()}
        />
      </ul>
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
