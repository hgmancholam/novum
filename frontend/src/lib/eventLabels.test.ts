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

    it("returns the base plan narrative when complexity_hint is absent", () => {
      const result = getEventNarrative("PlanCreated", {});
      expect(result).toBe("Drafted the search plan");
    });

    it("appends complexity to the plan narrative when present", () => {
      const result = getEventNarrative("PlanCreated", {
        complexity_hint: "deep",
      });
      expect(result).toBe("Drafted the search plan — deep investigation");
    });

    it("surfaces classification and complexity for QuestionClassified", () => {
      const result = getEventNarrative("QuestionClassified", {
        detected_question_type: "comparative",
        complexity_hint: "standard",
      });
      expect(result).toBe(
        "Classified as comparative question — Standard research"
      );
    });

    // IP-26 slice 3c — meta-judge event narratives (BRD-26).
    it("for MetaStopVerdict surfaces decision and expected delta", () => {
      const result = getEventNarrative("MetaStopVerdict", {
        verdict: { decision: "stop_best_effort", expected_delta_s: 0.01 },
      });
      expect(result).toContain("stop_best_effort");
      expect(result).toContain("0.01");
    });

    it("for MetaStopVerdict without delta still includes the decision", () => {
      const result = getEventNarrative("MetaStopVerdict", {
        verdict: { decision: "continue" },
      });
      expect(result).toContain("continue");
    });

    it("for MetaStopVerdict with no verdict falls back to a generic phrase", () => {
      const result = getEventNarrative("MetaStopVerdict", {});
      expect(result).toMatch(/meta-judge/i);
    });

    it("for AdversarialObjectionsGenerated highlights all_answered=true", () => {
      const result = getEventNarrative("AdversarialObjectionsGenerated", {
        verdict: { all_answered: true },
      });
      expect(result).toMatch(/already answered/i);
    });

    it("for AdversarialObjectionsGenerated highlights unresolved objections", () => {
      const result = getEventNarrative("AdversarialObjectionsGenerated", {
        verdict: { all_answered: false },
      });
      expect(result).toMatch(/unresolved/i);
    });

    it("for DirectedSubclaimsFromObjections pluralises by id count", () => {
      const single = getEventNarrative("DirectedSubclaimsFromObjections", {
        new_subclaim_ids: ["a"],
      });
      expect(single).toBe("Added 1 new sub-claim from an unresolved objection");
      const multi = getEventNarrative("DirectedSubclaimsFromObjections", {
        new_subclaim_ids: ["a", "b", "c"],
      });
      expect(multi).toBe("Added 3 new sub-claims from unresolved objections");
    });
  });
});
