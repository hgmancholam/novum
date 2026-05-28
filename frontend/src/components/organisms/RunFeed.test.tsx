import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { axe } from "jest-axe";
import { RunFeed } from "./RunFeed";
import type { RunStreamEvent } from "@/types/events";

// IntersectionObserver stub
class IntersectionObserverStub {
  callback: IntersectionObserverCallback;
  constructor(callback: IntersectionObserverCallback) {
    this.callback = callback;
  }
  observe(target: Element): void {
    // Simulate immediate intersection
    this.callback(
      [{ isIntersecting: true, target } as IntersectionObserverEntry],
      this as unknown as IntersectionObserver
    );
  }
  disconnect(): void {}
  unobserve(): void {}
  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
  get root(): Element | Document | null {
    return null;
  }
  get rootMargin(): string {
    return "";
  }
  get thresholds(): ReadonlyArray<number> {
    return [];
  }
}

describe("RunFeed", () => {
  let originalIntersectionObserver: typeof IntersectionObserver | undefined;

  beforeEach(() => {
    originalIntersectionObserver = globalThis.IntersectionObserver;
    globalThis.IntersectionObserver =
      IntersectionObserverStub as unknown as typeof IntersectionObserver;
    localStorage.clear();

    // Mock scrollIntoView
    Element.prototype.scrollIntoView = vi.fn();
  });

  afterEach(() => {
    if (originalIntersectionObserver) {
      globalThis.IntersectionObserver = originalIntersectionObserver;
    }
    vi.clearAllMocks();
  });

  const mockToolCalledEvent: RunStreamEvent = {
    type: "ToolCalled",
    step_index: 1,
    query: "AI systems",
    timestamp_ms: 1000,
  };

  const mockEvidenceEvent: RunStreamEvent = {
    type: "EvidenceAdded",
    step_index: 2,
    source_url: "https://example.com",
    source_title: "Example",
    timestamp_ms: 2000,
  };

  it("renders null when events is empty", () => {
    const { container } = render(
      <RunFeed events={[]} isComplete={false} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders SearchStepCard for ToolCalled + EvidenceAdded", async () => {
    render(
      <RunFeed
        events={[mockToolCalledEvent, mockEvidenceEvent]}
        isComplete={true}
      />
    );
    expect(await screen.findByText(/"AI systems"/)).toBeInTheDocument();
    expect(screen.getByText(/1 source/)).toBeInTheDocument();
  });

  it("renders PlanStepCard for PlanCreated", async () => {
    const planEvent: RunStreamEvent = {
      type: "PlanCreated",
      step_index: 1,
      rationale: "Breaking down the question",
      sub_claims: [
        { id: "1", text: "Claim 1", status: "pending" },
      ],
      timestamp_ms: 1000,
    };
    render(<RunFeed events={[planEvent]} isComplete={true} />);
    expect(await screen.findByText(/Breaking down the question/)).toBeInTheDocument();
  });

  it("renders JudgeVerdictCard for JudgeRuled", async () => {
    const judgeEvent: RunStreamEvent = {
      type: "JudgeRuled",
      step_index: 1,
      passed: true,
      final_confidence: 0.85,
      threshold: 0.7,
      rationale: "Good answer",
      timestamp_ms: 1000,
    };
    render(<RunFeed events={[judgeEvent]} isComplete={true} />);
    expect(await screen.findByText(/Confirmed/)).toBeInTheDocument();
    expect(screen.getByText(/85%/)).toBeInTheDocument();
  });

  it("shows collapse header when isComplete and has events", () => {
    render(
      <RunFeed
        events={[mockToolCalledEvent]}
        isComplete={true}
      />
    );
    expect(screen.getByRole("button", { name: /hide/i })).toBeInTheDocument();
  });

  it("does not show collapse button when not complete", () => {
    render(
      <RunFeed
        events={[mockToolCalledEvent]}
        isComplete={false}
      />
    );
    expect(screen.queryByRole("button", { name: /hide/i })).not.toBeInTheDocument();
  });

  it("collapses feed when toggle is clicked", async () => {
    const user = userEvent.setup();
    render(
      <RunFeed
        events={[mockToolCalledEvent]}
        isComplete={true}
      />
    );

    const toggle = screen.getByRole("button", { name: /hide/i });
    await user.click(toggle);

    expect(screen.queryByText(/"AI systems"/)).not.toBeInTheDocument();
  });

  it("persists collapsed state in localStorage", async () => {
    const user = userEvent.setup();
    render(
      <RunFeed
        events={[mockToolCalledEvent]}
        isComplete={true}
      />
    );

    const toggle = screen.getByRole("button", { name: /hide/i });
    await user.click(toggle);

    expect(localStorage.getItem("novum_run_feed_collapsed")).toBe("1");
  });

  it("shows JumpToLatestPill when not sticky", async () => {
    // Mock IntersectionObserver to simulate not sticky
    globalThis.IntersectionObserver = class {
      callback: IntersectionObserverCallback;
      constructor(callback: IntersectionObserverCallback) {
        this.callback = callback;
      }
      observe(target: Element): void {
        this.callback(
          [{ isIntersecting: false, target } as IntersectionObserverEntry],
          this as unknown as IntersectionObserver
        );
      }
      disconnect(): void {}
      unobserve(): void {}
      takeRecords(): IntersectionObserverEntry[] {
        return [];
      }
      get root(): Element | Document | null {
        return null;
      }
      get rootMargin(): string {
        return "";
      }
      get thresholds(): ReadonlyArray<number> {
        return [];
      }
    } as unknown as typeof IntersectionObserver;

    render(
      <RunFeed
        events={[mockToolCalledEvent]}
        isComplete={false}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Jump to latest")).toBeInTheDocument();
    });
  });

  it("has no a11y violations", async () => {
    const { container } = render(
      <RunFeed
        events={[mockToolCalledEvent, mockEvidenceEvent]}
        isComplete={false}
      />
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
