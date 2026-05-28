import { describe, it, expect } from "vitest";
import {
  buildFeedSteps,
  type RunStreamEvent,
} from "./feedGrouping";

describe("feedGrouping — IP-24 Phase 3", () => {
  // Helper to create events with consistent timestamps
  function makeEvent(
    type: string,
    overrides: Partial<RunStreamEvent> = {}
  ): RunStreamEvent {
    return {
      type,
      step_index: 0,
      timestamp_ms: Date.now(),
      ...overrides,
    };
  }

  it("(a) groups ToolCalled + 3× EvidenceAdded with same target_claim_id into one search bucket", () => {
    const events: RunStreamEvent[] = [
      makeEvent("ToolCalled", {
        query: "AI systems",
        target_claim_id: "claim-1",
      }),
      makeEvent("EvidenceAdded", {
        source_url: "https://example.com/1",
        source_title: "Source 1",
        target_claim_id: "claim-1",
      }),
      makeEvent("EvidenceAdded", {
        source_url: "https://example.com/2",
        source_title: "Source 2",
        target_claim_id: "claim-1",
      }),
      makeEvent("EvidenceAdded", {
        source_url: "https://example.com/3",
        source_title: "Source 3",
        target_claim_id: "claim-1",
      }),
    ];

    const steps = buildFeedSteps(events);
    expect(steps).toHaveLength(1);
    expect(steps[0]?.kind).toBe("search");
    const payload = steps[0]?.payload as { query: string; sources: unknown[] };
    expect(payload?.query).toBe("AI systems");
    expect(payload?.sources).toHaveLength(3);
  });

  it("(b) closes ToolCalled bucket when interrupted by ContradictionDetected", () => {
    const events: RunStreamEvent[] = [
      makeEvent("ToolCalled", { query: "test" }),
      makeEvent("EvidenceAdded", {
        source_url: "https://example.com/1",
        source_title: "Source 1",
      }),
      makeEvent("ContradictionDetected", {
        conflicting_sources: [],
      }),
    ];

    const steps = buildFeedSteps(events);
    expect(steps).toHaveLength(2);
    expect(steps[0]?.kind).toBe("search");
    expect(steps[1]?.kind).toBe("contradiction");
  });

  it("(c) full sequence PlanCreated → ToolCalled → EvidenceAdded → JudgeRuled → Stopped", () => {
    const events: RunStreamEvent[] = [
      makeEvent("PlanCreated", { sub_claims: [] }),
      makeEvent("ToolCalled", { query: "test" }),
      makeEvent("EvidenceAdded", {
        source_url: "https://example.com/1",
        source_title: "Source 1",
      }),
      makeEvent("JudgeRuled", { final_confidence: 0.85 }),
      makeEvent("Stopped", { stop_reason: "judge_confirmed" }),
    ];

    const steps = buildFeedSteps(events);
    expect(steps).toHaveLength(4);
    expect(steps.map((s) => s.kind)).toEqual([
      "plan",
      "search",
      "judge",
      "done",
    ]);
  });

  it("(d) appends SourceFailed to active search bucket", () => {
    const events: RunStreamEvent[] = [
      makeEvent("ToolCalled", { query: "test" }),
      makeEvent("EvidenceAdded", {
        source_url: "https://example.com/1",
        source_title: "Source 1",
      }),
      makeEvent("SourceFailed", {
        source_url: "https://example.com/failed",
        source_title: "Failed Source",
        error_type: "timeout",
      }),
    ];

    const steps = buildFeedSteps(events);
    expect(steps).toHaveLength(1);
    expect(steps[0]?.kind).toBe("search");
    const payload = steps[0]?.payload as { sources: unknown[] };
    expect(payload?.sources).toHaveLength(2);
  });

  it("(e) orphan EvidenceAdded without prior ToolCalled renders as generic", () => {
    const events: RunStreamEvent[] = [
      makeEvent("EvidenceAdded", {
        source_url: "https://example.com/1",
        source_title: "Orphan",
      }),
    ];

    const steps = buildFeedSteps(events);
    expect(steps).toHaveLength(1);
    expect(steps[0]?.kind).toBe("generic");
  });

  it("(f) isComplete=false → last step is marked isActive; isComplete=true → no active", () => {
    const events: RunStreamEvent[] = [
      makeEvent("PlanCreated", { sub_claims: [] }),
      makeEvent("ToolCalled", { query: "test" }),
    ];

    const stepsInProgress = buildFeedSteps(events, { isComplete: false });
    expect(stepsInProgress[stepsInProgress.length - 1]?.isActive).toBe(true);

    const stepsComplete = buildFeedSteps(events, { isComplete: true });
    expect(stepsComplete[stepsComplete.length - 1]?.isActive).toBeUndefined();
  });

  it("handles multiple ToolCalled in sequence (each closes previous bucket)", () => {
    const events: RunStreamEvent[] = [
      makeEvent("ToolCalled", { query: "first" }),
      makeEvent("EvidenceAdded", {
        source_url: "https://example.com/1",
        source_title: "Source 1",
      }),
      makeEvent("ToolCalled", { query: "second" }),
      makeEvent("EvidenceAdded", {
        source_url: "https://example.com/2",
        source_title: "Source 2",
      }),
    ];

    const steps = buildFeedSteps(events);
    expect(steps).toHaveLength(2);
    expect(steps[0]?.kind).toBe("search");
    expect((steps[0]?.payload as { query: string })?.query).toBe("first");
    expect(steps[1]?.kind).toBe("search");
    expect((steps[1]?.payload as { query: string })?.query).toBe("second");
  });

  it("does not group evidence with mismatched target_claim_id", () => {
    const events: RunStreamEvent[] = [
      makeEvent("ToolCalled", {
        query: "test",
        target_claim_id: "claim-1",
      }),
      makeEvent("EvidenceAdded", {
        source_url: "https://example.com/1",
        source_title: "Source 1",
        target_claim_id: "claim-1",
      }),
      makeEvent("EvidenceAdded", {
        source_url: "https://example.com/2",
        source_title: "Source 2",
        target_claim_id: "claim-2", // different claim
      }),
    ];

    const steps = buildFeedSteps(events);
    // First bucket closes with 1 source, second evidence becomes generic
    expect(steps).toHaveLength(2);
    expect(steps[0]?.kind).toBe("search");
    const payload = steps[0]?.payload as { sources: unknown[] };
    expect(payload?.sources).toHaveLength(1);
    expect(steps[1]?.kind).toBe("generic");
  });
});
