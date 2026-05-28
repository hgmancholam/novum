/**
 * Friendly labels for the event types emitted by the agent.
 *
 * Two related maps:
 *
 * - `EVENT_LABELS` — short noun phrase used in the trace timeline
 *   (e.g. "Plan" instead of "PlanCreated").
 * - `EVENT_ACTIVITIES` — present-continuous activity used in the live
 *   "researching" indicator (e.g. "Drafting a plan" while `PlanCreated`
 *   is the latest event).
 *
 * Both are keyed by the raw `EventType` string so unknown values fall
 * back to the raw type. See ui-prototype.md §7 (microcopy).
 */

import type { EventType } from "@/types/events";

export const EVENT_LABELS: Record<EventType, string> = {
  QuestionAsked: "Question",
  QuestionNormalized: "Question rephrased",
  QuestionClassified: "Question type",
  PlanCreated: "Plan",
  PlanCritiqued: "Plan critique",
  PlanRevised: "Plan revised",
  ToolCalled: "Search",
  EvidenceAdded: "Evidence",
  ClaimCovered: "Claim covered",
  ClaimUncoverable: "Claim without evidence",
  SourceFailed: "Source unavailable",
  AmbiguityDetected: "Ambiguity",
  ContradictionDetected: "Contradiction",
  ContradictionResolved: "Contradiction resolved",
  UserContextChallenged: "Context challenged",
  PriorRunHintReplayed: "Prior result reused",
  JudgeRuled: "Judge verdict",
  ConfidenceMismatch: "Confidence mismatch",
  AgentErrored: "Agent error",
  ResumedAfterError: "Resumed after error",
  ResumedAfterCancel: "Resumed after cancel",
  Stopped: "Done",
  SaturationDetected: "Saturation",
  JudgeProviderDegraded: "Judge degraded",
  DeepFetchPerformed: "Deep read",
};

export const EVENT_ACTIVITIES: Record<EventType, string> = {
  QuestionAsked: "Got your question",
  QuestionNormalized: "Rephrasing the question to understand it better",
  QuestionClassified: "Figuring out what kind of question this is",
  PlanCreated: "Drafting a search plan",
  PlanCritiqued: "Reviewing the plan before moving on",
  PlanRevised: "Rethinking the approach",
  ToolCalled: "Searching the web",
  EvidenceAdded: "Reading what I found",
  ClaimCovered: "Marking a claim as covered",
  ClaimUncoverable: "Identifying gaps in the evidence",
  SourceFailed: "Retrying a source",
  AmbiguityDetected: "Detecting ambiguity in the question",
  ContradictionDetected: "Found contradictory information",
  ContradictionResolved: "Reconciling what the sources say",
  UserContextChallenged: "I need a bit more context",
  PriorRunHintReplayed: "Recovering a previous answer",
  JudgeRuled: "Judging whether the answer is good enough",
  ConfidenceMismatch: "Reviewing confidence levels",
  AgentErrored: "Recovering from an error",
  ResumedAfterError: "Picking up where I left off",
  ResumedAfterCancel: "Picking up where I left off",
  Stopped: "Wrapping up",
  SaturationDetected: "Detecting saturation",
  JudgeProviderDegraded: "Switching to a backup judge",
  DeepFetchPerformed: "Reading the full page",
};

export function getEventLabel(type: string): string {
  return EVENT_LABELS[type as EventType] ?? type;
}

export function getEventActivity(type: string | undefined): string {
  if (type === undefined || type === "") {
    return "Working on it";
  }
  return EVENT_ACTIVITIES[type as EventType] ?? "Working on it";
}

/**
 * Enhanced narrative for feed display — returns a richer natural-language
 * phrase than EVENT_ACTIVITIES. Falls back to getEventActivity for unmapped types.
 */
export function getEventNarrative(
  type: EventType,
  payload: Record<string, unknown>,
): string {
  switch (type) {
    case "ToolCalled": {
      const query = payload["query"];
      if (typeof query === "string" && query.length > 0) {
        return `Searched the web: "${query}"`;
      }
      return "Searched the web";
    }
    case "EvidenceAdded": {
      const title = payload["source_title"];
      const url = payload["source_url"];
      if (typeof title === "string" && typeof url === "string") {
        try {
          const hostname = new URL(url).hostname.replace(/^www\./, "");
          return `Read "${title}" (${hostname})`;
        } catch {
          return `Read "${title}"`;
        }
      }
      return "Read a source";
    }
    case "JudgeRuled": {
      const confidence = payload["final_confidence"];
      if (typeof confidence === "number") {
        return `Judge verdict: confidence ${confidence.toFixed(2)}`;
      }
      return "The judge evaluated the answer";
    }
    case "Stopped": {
      const stopReason = payload["stop_reason"];
      if (typeof stopReason === "string") {
        return `Done — ${stopReason}`;
      }
      return "Done";
    }
    default:
      return getEventActivity(type);
  }
}
