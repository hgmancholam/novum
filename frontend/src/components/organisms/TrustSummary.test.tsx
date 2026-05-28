import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";

import { TrustSummary } from "./TrustSummary";
import type { Run } from "@/types/run";

function makeRun(overrides: Partial<Run> = {}): Run {
  return {
    id: "00000000-0000-0000-0000-000000000001",
    ownerUsername: "alice",
    question: "Q?",
    userContext: null,
    questionType: "factual",
    outputFormat: "structured",
    confidenceThreshold: 0.7,
    startedAt: "2026-05-26T00:00:00Z",
    stoppedAt: "2026-05-26T00:01:00Z",
    stopReason: "stopped_by_budget",
    parentRunId: null,
    forkedAtEventId: null,
    llmProvider: "github",
    ...overrides,
  };
}

describe("TrustSummary", () => {
  it("renders the outcome title and the threshold", () => {
    render(<TrustSummary run={makeRun()} />);
    expect(screen.getByText("Research Limit Reached")).toBeInTheDocument();
    expect(screen.getByText("0.70")).toBeInTheDocument();
  });

  it("renders em-dash placeholders for event-derived metrics", () => {
    render(<TrustSummary run={makeRun()} />);
    // confidence + sources are pending (event log) — Iterations row removed
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(2);
  });

  it("shows live confidence metrics when judgeConfidence is provided", () => {
    const metrics = {
      finalConfidence: 0.85,
      structuralConfidence: 0.9,
      judgeConfidence: 0.85,
      passed: true,
    };
    render(<TrustSummary run={makeRun({ stopReason: "judge_confirmed" })} judgeConfidence={metrics} />);
    expect(screen.getByText("85%")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: /Confidence 85%/i })).toBeInTheDocument();
    // No pending placeholder for confidence
    expect(screen.queryAllByText("—").length).toBeLessThan(2);
  });

  it("shows source count when provided", () => {
    render(<TrustSummary run={makeRun()} sourceCount={7} />);
    expect(screen.getByText("7 sources")).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<TrustSummary run={makeRun()} />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
