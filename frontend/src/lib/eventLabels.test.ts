import { describe, expect, it } from "vitest";

import {
  EVENT_ACTIVITIES,
  EVENT_LABELS,
  getEventActivity,
  getEventLabel,
} from "./eventLabels";

const ALL_EVENT_TYPES = [
  "QuestionAsked",
  "QuestionNormalized",
  "PlanCreated",
  "PlanCritiqued",
  "PlanRevised",
  "ToolCalled",
  "EvidenceAdded",
  "ClaimCovered",
  "ClaimUncoverable",
  "SourceFailed",
  "AmbiguityDetected",
  "ContradictionDetected",
  "ContradictionResolved",
  "UserContextChallenged",
  "JudgeRuled",
  "ConfidenceMismatch",
  "AgentErrored",
  "ResumedAfterError",
  "ResumedAfterCancel",
  "Stopped",
] as const;

describe("eventLabels", () => {
  it("has a label and activity for every EventType", () => {
    for (const type of ALL_EVENT_TYPES) {
      expect(EVENT_LABELS[type]).toBeTruthy();
      expect(EVENT_ACTIVITIES[type]).toBeTruthy();
    }
  });

  it("getEventLabel returns the friendly name", () => {
    expect(getEventLabel("PlanCreated")).toBe("Plan");
    expect(getEventLabel("ToolCalled")).toBe("Search");
  });

  it("getEventLabel falls back to the raw type for unknown events", () => {
    expect(getEventLabel("SomeFutureEvent")).toBe("SomeFutureEvent");
  });

  it("getEventActivity returns a present-continuous phrase", () => {
    expect(getEventActivity("PlanCreated")).toMatch(/plan/i);
    expect(getEventActivity("ToolCalled")).toMatch(/search/i);
  });

  it("getEventActivity falls back to a generic activity", () => {
    expect(getEventActivity(undefined)).toBe("Working on it");
    expect(getEventActivity("")).toBe("Working on it");
    expect(getEventActivity("Unknown")).toBe("Working on it");
  });
});
