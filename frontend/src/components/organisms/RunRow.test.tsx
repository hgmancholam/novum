import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { axe } from "jest-axe";

import { RunRow } from "./RunRow";
import type { RunSummary } from "@/types/history";

const baseRun: RunSummary = {
  id: "run-1",
  question: "What is the population of Tokyo in 2024?",
  status: "completed",
  stopReason: "judge_confirmed",
  startedAt: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
  stoppedAt: null,
};

describe("RunRow", () => {
  it("renders truncated question, status, and relative time", () => {
    render(<RunRow run={baseRun} isSelected={false} onSelect={() => {}} />);
    expect(
      screen.getByText("What is the population of Tokyo in 2024?")
    ).toBeInTheDocument();
    expect(screen.getByText("Judge confirmed")).toBeInTheDocument();
    expect(screen.getByText(/m ago|just now/)).toBeInTheDocument();
  });

  it("truncates questions longer than 60 chars with an ellipsis", () => {
    const longRun: RunSummary = {
      ...baseRun,
      question:
        "This is a very long research question that should definitely be truncated past sixty characters for readability.",
    };
    render(<RunRow run={longRun} isSelected={false} onSelect={() => {}} />);
    const node = screen.getByTestId("run-row");
    expect(node.textContent).toMatch(/…/);
  });

  it("marks selection state via data-selected and aria-current", () => {
    render(<RunRow run={baseRun} isSelected={true} onSelect={() => {}} />);
    const node = screen.getByTestId("run-row");
    expect(node).toHaveAttribute("data-selected", "true");
    expect(node).toHaveAttribute("aria-current", "true");
  });

  it("invokes onSelect with run id on click", () => {
    const onSelect = vi.fn();
    render(<RunRow run={baseRun} isSelected={false} onSelect={onSelect} />);
    fireEvent.click(screen.getByTestId("run-row"));
    expect(onSelect).toHaveBeenCalledWith("run-1");
  });

  it("renders running status without stopReason", () => {
    const runningRun: RunSummary = {
      ...baseRun,
      status: "running",
      stopReason: null,
      stoppedAt: null,
    };
    render(<RunRow run={runningRun} isSelected={false} onSelect={() => {}} />);
    expect(screen.getByText("Researching…")).toBeInTheDocument();
  });

  it("has no a11y violations", async () => {
    const { container } = render(
      <RunRow run={baseRun} isSelected={false} onSelect={() => {}} />
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
