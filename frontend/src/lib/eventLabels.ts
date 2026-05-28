/**
 * Friendly labels for the 20 event types emitted by the agent.
 *
 * Two related maps:
 *
 * - `EVENT_LABELS` — short noun phrase used in the trace timeline
 *   (e.g. "Plan" instead of "PlanCreated").
 * - `EVENT_ACTIVITIES` — present-continuous activity used in the live
 *   "researching" indicator (e.g. "Drafting a plan" while `PlanCreated`
 *   is the latest event).
 *
 * Both are keyed by the raw `EventType` string so unknown values (e.g.
 * future event types not yet generated into `types/events.ts`) fall back
 * to the raw type. See ui-prototype.md §7 (microcopy).
 */

import type { EventType } from "@/types/events";

export const EVENT_LABELS: Record<EventType, string> = {
  QuestionAsked: "Question",
  QuestionNormalized: "Normalized question",
  QuestionClassified: "Question classified",
  PlanCreated: "Plan",
  PlanCritiqued: "Plan critique",
  PlanRevised: "Plan revision",
  ToolCalled: "Search",
  EvidenceAdded: "Evidence",
  ClaimCovered: "Claim covered",
  ClaimUncoverable: "Claim uncoverable",
  SourceFailed: "Source failed",
  AmbiguityDetected: "Ambiguity",
  ContradictionDetected: "Contradiction",
  ContradictionResolved: "Contradiction resolved",
  UserContextChallenged: "Context challenged",
  PriorRunHintReplayed: "Prior result reused",
  JudgeRuled: "Judge ruling",
  ConfidenceMismatch: "Confidence mismatch",
  AgentErrored: "Agent error",
  ResumedAfterError: "Resumed after error",
  ResumedAfterCancel: "Resumed after cancel",
  Stopped: "Stopped",
  SaturationDetected: "Saturation",
  JudgeProviderDegraded: "Judge degraded",
  DeepFetchPerformed: "Deep fetch",
};

export const EVENT_ACTIVITIES: Record<EventType, string> = {
  QuestionAsked: "Reading your question",
  QuestionNormalized: "Understanding the question",
  QuestionClassified: "Classifying the question",
  PlanCreated: "Drafting a plan",
  PlanCritiqued: "Reviewing the plan",
  PlanRevised: "Refining the plan",
  ToolCalled: "Searching the web",
  EvidenceAdded: "Reading evidence",
  ClaimCovered: "Checking claims",
  ClaimUncoverable: "Marking gaps",
  SourceFailed: "Retrying a source",
  AmbiguityDetected: "Spotting ambiguity",
  ContradictionDetected: "Spotting a contradiction",
  ContradictionResolved: "Reconciling sources",
  UserContextChallenged: "Asking for context",
  PriorRunHintReplayed: "Retrieving cached answer",
  JudgeRuled: "Judging the answer",
  ConfidenceMismatch: "Reviewing confidence",
  AgentErrored: "Recovering from an error",
  ResumedAfterError: "Picking up where it left off",
  ResumedAfterCancel: "Picking up where it left off",
  Stopped: "Wrapping up",
  SaturationDetected: "Detecting saturation",
  JudgeProviderDegraded: "Switching judge provider",
  DeepFetchPerformed: "Fetching full page",
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
