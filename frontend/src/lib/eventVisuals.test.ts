import { describe, it, expect } from "vitest";

import {
  EVENT_VISUALS,
  EXPANDED_BY_DEFAULT,
  DECISION_EVENTS,
  TONE_COLOR,
  getEventVisual,
  isDecisionEvent,
  type EventTone,
} from "./eventVisuals";
import type { EventType } from "@/types/events";

const ALL_EVENT_TYPES: readonly EventType[] = [
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
];

describe("eventVisuals", () => {
  it("maps every EventType to a visual", () => {
    for (const t of ALL_EVENT_TYPES) {
      expect(EVENT_VISUALS[t]).toBeDefined();
      expect(EVENT_VISUALS[t].Icon).toBeDefined();
      expect(EVENT_VISUALS[t].tone).toBeDefined();
    }
  });

  it("uses only valid tones", () => {
    const valid: readonly EventTone[] = [
      "info",
      "success",
      "warn",
      "danger",
      "neutral",
      "judge",
      "decision",
    ];
    for (const t of ALL_EVENT_TYPES) {
      expect(valid).toContain(EVENT_VISUALS[t].tone);
    }
  });

  it("TONE_COLOR has an entry for every tone used", () => {
    for (const t of ALL_EVENT_TYPES) {
      expect(TONE_COLOR[EVENT_VISUALS[t].tone]).toMatch(/^var\(--/);
    }
  });

  it("seeds JudgeRuled as expanded-by-default and only that", () => {
    expect(EXPANDED_BY_DEFAULT.has("JudgeRuled")).toBe(true);
    expect(EXPANDED_BY_DEFAULT.has("QuestionAsked")).toBe(false);
    expect(EXPANDED_BY_DEFAULT.size).toBe(1);
  });

  it("marks the documented decision events", () => {
    for (const t of [
      "PlanCreated",
      "JudgeRuled",
      "ContradictionDetected",
      "AmbiguityDetected",
      "Stopped",
    ] as const) {
      expect(DECISION_EVENTS.has(t)).toBe(true);
      expect(isDecisionEvent(t)).toBe(true);
    }
    expect(isDecisionEvent("EvidenceAdded")).toBe(false);
    expect(isDecisionEvent("unknown-synthetic")).toBe(false);
  });

  it("getEventVisual falls back for unknown types", () => {
    const v = getEventVisual("cancelled");
    expect(v.tone).toBe("neutral");
    expect(v.Icon).toBeDefined();
  });

  it("getEventVisual returns the mapped value for known types", () => {
    const v = getEventVisual("JudgeRuled");
    expect(v.tone).toBe("judge");
  });
});
