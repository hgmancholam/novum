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
    // confidence / iterations / sources are pending (event log)
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(3);
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<TrustSummary run={makeRun()} />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
