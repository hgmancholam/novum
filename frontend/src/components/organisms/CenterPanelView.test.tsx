import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { CenterPanelView } from "./CenterPanelView";
import type { Run } from "@/types/run";

function makeRun(overrides: Partial<Run> = {}): Run {
  return {
    id: "00000000-0000-0000-0000-000000000001",
    ownerUsername: "alice",
    question: "Is the Earth round?",
    userContext: null,
    questionType: "factual",
    outputFormat: "prose",
    confidenceThreshold: 0.7,
    startedAt: "2026-05-26T00:00:00Z",
    stoppedAt: null,
    stopReason: null,
    parentRunId: null,
    forkedAtEventId: null,
    llmProvider: "github",
    ...overrides,
  };
}

describe("CenterPanelView", () => {
  beforeEach(() => {
    // Mock scrollIntoView for RunFeed (IP-24)
    Element.prototype.scrollIntoView = vi.fn();
  });
  it("renders the question and the RunFeed while running (IP-24)", () => {
    const mockEvents = [
      {
        type: "ToolCalled",
        step_index: 1,
        query: "test query",
        timestamp_ms: 1000,
      },
    ];
    render(
      <CenterPanelView run={makeRun()} status="running" events={mockEvents} />
    );
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Is the Earth round?"
    );
    expect(screen.getByTestId("run-feed")).toBeInTheDocument();
    expect(screen.queryByTestId("stop-reason-card")).not.toBeInTheDocument();
  });

  it("renders the StopReasonCard once the run has stopped", () => {
    const run = makeRun({
      stoppedAt: "2026-05-26T00:05:00Z",
      stopReason: "judge_confirmed",
    });
    render(<CenterPanelView run={run} status="stopped" />);
    expect(screen.getByTestId("stop-reason-card")).toHaveAttribute(
      "data-reason",
      "judge_confirmed"
    );
    expect(screen.queryByTestId("run-feed")).not.toBeInTheDocument();
  });

  it("renders only the question when status=stopped but stop_reason is null", () => {
    const run = makeRun({ stoppedAt: "2026-05-26T00:05:00Z", stopReason: null });
    render(<CenterPanelView run={run} status="stopped" />);
    expect(screen.queryByTestId("stop-reason-card")).not.toBeInTheDocument();
    expect(screen.queryByTestId("run-feed")).not.toBeInTheDocument();
  });
});
