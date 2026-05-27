import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { RunHeader } from "./RunHeader";
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
    stoppedAt: null,
    stopReason: null,
    parentRunId: null,
    forkedAtEventId: null,
    ...overrides,
  };
}

describe("RunHeader", () => {
  it("shows the Researching badge and elapsed clock while running", () => {
    render(<RunHeader run={makeRun()} status="running" />);
    expect(screen.getByText("Researching…")).toBeInTheDocument();
    expect(screen.getByTestId("elapsed-clock")).toBeInTheDocument();
    expect(screen.getByTestId("meta-row")).toBeInTheDocument();
  });

  it("shows the stop_reason microcopy when terminal and hides the clock", () => {
    const run = makeRun({
      stoppedAt: "2026-05-26T00:00:10Z",
      stopReason: "judge_confirmed",
    });
    render(<RunHeader run={run} status="stopped" />);
    expect(screen.getByText("Judge confirmed")).toBeInTheDocument();
    expect(screen.queryByTestId("elapsed-clock")).not.toBeInTheDocument();
  });
});
