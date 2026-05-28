import { describe, expect, it } from "vitest";

import {
  EVENT_ACTIVITIES,
  EVENT_LABELS,
  getEventActivity,
  getEventLabel,
  getEventNarrative,
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

  // IP-24 (Phase 0)
  describe("getEventNarrative", () => {
    it("for ToolCalled includes the query", () => {
      const result = getEventNarrative("ToolCalled", {
        query: "AI systems replacing engineers",
      });
      expect(result).toContain("Searched the web");
      expect(result).toContain("AI systems replacing engineers");
    });

    it("for ToolCalled without query falls back gracefully", () => {
      const result = getEventNarrative("ToolCalled", {});
      expect(result).toBe("Searched the web");
    });

    it("for EvidenceAdded includes title and hostname", () => {
      const result = getEventNarrative("EvidenceAdded", {
        source_title: "Understanding AI",
        source_url: "https://www.example.com/article",
      });
      expect(result).toContain("Read \"Understanding AI\"");
      expect(result).toContain("example.com");
    });

    it("for EvidenceAdded strips www prefix from hostname", () => {
      const result = getEventNarrative("EvidenceAdded", {
        source_title: "Tech News",
        source_url: "https://www.nytimes.com/article",
      });
      expect(result).toContain("nytimes.com");
      expect(result).not.toContain("www.nytimes.com");
    });

    it("for EvidenceAdded handles malformed URL gracefully", () => {
      const result = getEventNarrative("EvidenceAdded", {
        source_title: "Document",
        source_url: "not a url",
      });
      expect(result).toContain("Read \"Document\"");
    });

    it("for JudgeRuled includes confidence", () => {
      const result = getEventNarrative("JudgeRuled", {
        final_confidence: 0.85,
      });
      expect(result).toContain("Judge verdict: confidence");
      expect(result).toContain("0.85");
    });

    it("for Stopped includes stop_reason", () => {
      const result = getEventNarrative("Stopped", {
        stop_reason: "judge_confirmed",
      });
      expect(result).toContain("Done — judge_confirmed");
    });

    it("falls back to getEventActivity for unmapped types", () => {
      const result = getEventNarrative("PlanCreated", {});
      expect(result).toBe(getEventActivity("PlanCreated"));
    });
  });
});
