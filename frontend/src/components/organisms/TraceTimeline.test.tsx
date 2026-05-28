import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, within, act } from "@testing-library/react";
import { axe } from "jest-axe";

import {
  TraceTimeline,
  type TraceTimelineEvent,
} from "./TraceTimeline";

type IOEntry = { isIntersecting: boolean };
type IOCallback = (entries: IOEntry[]) => void;

interface FakeIO {
  observe: (node: Element) => void;
  disconnect: () => void;
  trigger: (intersecting: boolean) => void;
}

const ioInstances: FakeIO[] = [];

class FakeIntersectionObserver implements FakeIO {
  private cb: IOCallback;
  observe = vi.fn();
  disconnect = vi.fn();
  unobserve = vi.fn();
  takeRecords = vi.fn(() => []);
  root: Element | null = null;
  rootMargin = "";
  thresholds: ReadonlyArray<number> = [];

  constructor(cb: IOCallback) {
    this.cb = cb;
    ioInstances.push(this);
  }
  trigger(intersecting: boolean): void {
    this.cb([{ isIntersecting: intersecting }]);
  }
}

const scrollIntoViewMock = vi.fn();

beforeEach(() => {
  ioInstances.length = 0;
  scrollIntoViewMock.mockClear();
  vi.stubGlobal("IntersectionObserver", FakeIntersectionObserver);
  // jsdom does not implement scrollIntoView.
  Element.prototype.scrollIntoView = scrollIntoViewMock as unknown as (
    arg?: boolean | ScrollIntoViewOptions
  ) => void;
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function evt(
  type: string,
  overrides: Partial<TraceTimelineEvent> = {}
): TraceTimelineEvent {
  return { type, ...overrides };
}

describe("TraceTimeline", () => {
  it("renders PlanPreview when only a QuestionAsked event is present (T1b)", () => {
    render(
      <TraceTimeline
        events={[evt("QuestionAsked", { id: "q1", question: "why?" })]}
        isComplete={false}
      />
    );
    expect(screen.getByTestId("plan-preview")).toBeInTheDocument();
    // The single QuestionAsked is still rendered as a node.
    expect(screen.getAllByTestId("event-node")).toHaveLength(1);
  });

  it("does NOT render PlanPreview once non-Question events arrive", () => {
    render(
      <TraceTimeline
        events={[evt("QuestionAsked"), evt("PlanCreated"), evt("ToolCalled")]}
        isComplete={false}
      />
    );
    expect(screen.queryByTestId("plan-preview")).toBeNull();
    expect(screen.getAllByTestId("event-node")).toHaveLength(3);
  });

  it("renders PlanPreview when events list is empty (T1b)", () => {
    render(<TraceTimeline events={[]} isComplete={false} />);
    expect(screen.getByTestId("plan-preview")).toBeInTheDocument();
    expect(screen.queryAllByTestId("event-node")).toHaveLength(0);
  });

  it("seeds JudgeRuled events into the expanded set on arrival", () => {
    render(
      <TraceTimeline
        events={[
          evt("QuestionAsked"),
          evt("JudgeRuled", { id: "j1", verdict: "confirmed" }),
        ]}
        isComplete={false}
      />
    );
    // Two nodes; the JudgeRuled one must already be expanded.
    const nodes = screen.getAllByTestId("event-node");
    const judge = nodes.find(
      (n) => n.getAttribute("data-event-type") === "JudgeRuled"
    );
    expect(judge).toBeDefined();
    expect(judge!.getAttribute("data-expanded")).toBe("true");
    // Its payload viewer is visible.
    expect(within(judge!).getByTestId("event-payload-viewer")).toBeInTheDocument();
  });

  it("toggles a node expand/collapse via the toggle button", () => {
    render(
      <TraceTimeline
        events={[evt("PlanCreated", { id: "p1" })]}
        isComplete={false}
      />
    );
    const node = screen.getByTestId("event-node");
    const btn = within(node).getByRole("button");
    expect(btn).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(btn);
    expect(btn).toHaveAttribute("aria-expanded", "true");
    expect(node.getAttribute("data-expanded")).toBe("true");

    fireEvent.click(btn);
    expect(btn).toHaveAttribute("aria-expanded", "false");
  });

  it("auto-scrolls to bottom when the sentinel is intersecting", () => {
    const { rerender } = render(
      <TraceTimeline
        events={[evt("PlanCreated", { id: "p1" })]}
        isComplete={false}
      />
    );
    // IntersectionObserver was installed.
    expect(ioInstances.length).toBeGreaterThan(0);
    const io = ioInstances[0]!;
    // Simulate sentinel in view → sticky=true.
    act(() => {
      io.trigger(true);
    });
    const callsBefore = scrollIntoViewMock.mock.calls.length;

    // New event arrives.
    rerender(
      <TraceTimeline
        events={[
          evt("PlanCreated", { id: "p1" }),
          evt("ToolCalled", { id: "t1" }),
        ]}
        isComplete={false}
      />
    );
    expect(scrollIntoViewMock.mock.calls.length).toBeGreaterThan(callsBefore);

    // Pill must NOT be visible while sticky.
    expect(screen.queryByTestId("jump-to-latest-pill")).toBeNull();
    expect(screen.getByTestId("trace-timeline").getAttribute("data-sticky")).toBe("true");
  });

  it("shows the JumpToLatestPill when the sentinel is NOT intersecting", () => {
    render(
      <TraceTimeline
        events={[
          evt("PlanCreated", { id: "p1" }),
          evt("ToolCalled", { id: "t1" }),
        ]}
        isComplete={false}
      />
    );
    const io = ioInstances[0]!;
    act(() => {
      io.trigger(false);
    });

    expect(screen.getByTestId("jump-to-latest-pill")).toBeInTheDocument();
    expect(screen.getByTestId("trace-timeline").getAttribute("data-sticky")).toBe(
      "false"
    );

    // Clicking the pill restores sticky.
    fireEvent.click(screen.getByTestId("jump-to-latest-pill"));
    expect(screen.getByTestId("trace-timeline").getAttribute("data-sticky")).toBe(
      "true"
    );
  });

  it("hides the JumpToLatestPill once the run is complete", () => {
    render(
      <TraceTimeline
        events={[evt("PlanCreated"), evt("ToolCalled")]}
        isComplete={true}
      />
    );
    act(() => {
      ioInstances[0]?.trigger(false);
    });
    expect(screen.queryByTestId("jump-to-latest-pill")).toBeNull();
  });

  it("uses stepIndex and deltaMs from payload for the meta line", () => {
    render(
      <TraceTimeline
        events={[
          evt("PlanCreated", { id: "p1", step_index: 1, timestamp_ms: 1000 }),
          evt("ToolCalled", { id: "t1", step_index: 2, timestamp_ms: 1500 }),
        ]}
        isComplete={false}
      />
    );
    const nodes = screen.getAllByTestId("event-node");
    expect(nodes[1]).toHaveTextContent("step 2");
    expect(nodes[1]).toHaveTextContent("Δ 500 ms");
  });

  it("has no accessibility violations", async () => {
    const { container } = render(
      <TraceTimeline
        events={[
          evt("QuestionAsked", { id: "q1", question: "hi" }),
          evt("PlanCreated", { id: "p1" }),
        ]}
        isComplete={false}
      />
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("renders PriorRunHintReplayed event correctly (IP-22)", () => {
    render(
      <TraceTimeline
        events={[
          evt("QuestionAsked", { id: "q1" }),
          evt("PriorRunHintReplayed", {
            id: "replay1",
            source_run_id: "run-456",
            source_final_confidence: 0.92,
            prior_completed_at: new Date().toISOString(),
          }),
        ]}
        isComplete={false}
      />
    );
    const nodes = screen.getAllByTestId("event-node");
    const replayNode = nodes.find(
      (n) => n.getAttribute("data-event-type") === "PriorRunHintReplayed"
    );
    expect(replayNode).toBeDefined();
    expect(replayNode).toHaveTextContent("Resultado reutilizado");
    expect(replayNode).toHaveTextContent("confidence 0.92");
  });
});
