import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { MemoryRouter, Routes, Route } from "react-router-dom";

import type { UseRunStreamResult } from "@/hooks/useRunStream";

const mockUseRunStream = vi.fn((_opts: unknown): UseRunStreamResult => streamResult());

vi.mock("@/hooks/useRunStream", () => ({
  useRunStream: (opts: unknown) => mockUseRunStream(opts),
}));

import { TracePanelContainer } from "./TracePanelContainer";

function streamResult(over: Partial<UseRunStreamResult> = {}): UseRunStreamResult {
  return {
    events: [],
    isConnected: false,
    isComplete: false,
    lastEventId: null,
    error: null,
    reconnect: vi.fn(),
    close: vi.fn(),
    ...over,
  };
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/" element={<TracePanelContainer />} />
        <Route path="/runs/:runId" element={<TracePanelContainer />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  mockUseRunStream.mockReset();
  // Provide a safe default so the hook contract is honored on every path.
  mockUseRunStream.mockReturnValue(streamResult());
  // jsdom lacks IO and scrollIntoView; provide minimal stubs.
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      observe = vi.fn();
      disconnect = vi.fn();
      unobserve = vi.fn();
      takeRecords = vi.fn(() => []);
      root = null;
      rootMargin = "";
      thresholds = [];
      constructor(_cb: unknown) {}
    }
  );
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("TracePanelContainer", () => {
  it("T1a: renders TraceEmpty when no runId is in the route", () => {
    renderAt("/");
    expect(screen.getByTestId("trace-empty")).toBeInTheDocument();
    expect(screen.queryByTestId("trace-timeline")).toBeNull();
    expect(screen.queryByTestId("trace-live-indicator")).toBeNull();

    // The hook is called but with enabled=false (no SSE subscription).
    expect(mockUseRunStream).toHaveBeenCalled();
    const lastCall = mockUseRunStream.mock.calls.at(-1)?.[0] as unknown as {
      runId: string | undefined;
      enabled: boolean;
    };
    expect(lastCall.runId).toBeUndefined();
    expect(lastCall.enabled).toBe(false);
  });

  it("T1b: renders PlanPreview and Live indicator when only QuestionAsked has arrived", () => {
    mockUseRunStream.mockReturnValue(
      streamResult({
        events: [{ type: "QuestionAsked", id: "q1" }],
        isConnected: true,
        isComplete: false,
      })
    );
    renderAt("/runs/abc");

    expect(screen.getByTestId("trace-timeline")).toBeInTheDocument();
    expect(screen.getByTestId("plan-preview")).toBeInTheDocument();
    expect(screen.getByTestId("trace-live-indicator")).toBeInTheDocument();

    const lastCall = mockUseRunStream.mock.calls.at(-1)?.[0] as unknown as {
      runId: string | undefined;
      enabled: boolean;
    };
    expect(lastCall.runId).toBe("abc");
    expect(lastCall.enabled).toBe(true);
  });

  it("T2: renders the full timeline and Live indicator while streaming", () => {
    mockUseRunStream.mockReturnValue(
      streamResult({
        events: [
          { type: "QuestionAsked", id: "q1" },
          { type: "PlanCreated", id: "p1" },
          { type: "ToolCalled", id: "t1" },
        ],
        isConnected: true,
        isComplete: false,
      })
    );
    renderAt("/runs/abc");

    expect(screen.getAllByTestId("event-node")).toHaveLength(3);
    expect(screen.queryByTestId("plan-preview")).toBeNull();
    expect(screen.getByTestId("trace-live-indicator")).toBeInTheDocument();
  });

  it("T3: hides the Live indicator once the run is complete", () => {
    mockUseRunStream.mockReturnValue(
      streamResult({
        events: [
          { type: "PlanCreated", id: "p1" },
          { type: "Stopped", id: "s1" },
        ],
        isConnected: false,
        isComplete: true,
      })
    );
    renderAt("/runs/abc");

    expect(screen.getByTestId("trace-timeline")).toBeInTheDocument();
    expect(screen.queryByTestId("trace-live-indicator")).toBeNull();
    expect(screen.queryByTestId("jump-to-latest-pill")).toBeNull();
  });

  it("has no accessibility violations in the streaming state", async () => {
    mockUseRunStream.mockReturnValue(
      streamResult({
        events: [
          { type: "QuestionAsked", id: "q1" },
          { type: "PlanCreated", id: "p1" },
        ],
        isConnected: true,
        isComplete: false,
      })
    );
    const { container } = renderAt("/runs/abc");
    expect(await axe(container)).toHaveNoViolations();
  });
});
