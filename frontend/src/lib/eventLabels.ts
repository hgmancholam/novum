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

import type { ComplexityHint, EventType, QuestionType } from "@/types/events";

export const COMPLEXITY_LABELS: Record<ComplexityHint, string> = {
  trivial: "Quick lookup",
  standard: "Standard research",
  deep: "Deep investigation",
};

export const QUESTION_TYPE_LABELS: Record<QuestionType, string> = {
  factual: "factual",
  comparative: "comparative",
  definitional: "definitional",
  state_of_art: "state-of-the-art",
  causal: "causal",
  predictive_future: "predictive",
  subjective_opinion: "opinion",
  personal_private: "personal",
};

export const EVENT_LABELS: Record<EventType, string> = {
  QuestionAsked: "Question",
  QuestionNormalized: "Question rephrased",
  QuestionClassified: "Question type",
  PlanCreated: "Plan",
  PlanCritiqued: "Plan critique",
  PlanRevised: "Plan revised",
  HypothesesGenerated: "Hypotheses generated",
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
  QueryReformulated: "Query refined",
  EchoChamberDetected: "Echo chamber",
  RouteSelected: "Route selected",
  PlanGapsDetected: "Plan gaps detected",
  NoProgressDetected: "No progress detected",
  LaneEscalated: "Lane escalated",
  AgentThought: "Agent thought",
  AgentAction: "Agent action",
  AgentObservation: "Observation",
  HypothesisEvaluated: "Hypothesis evaluated",
  HistorySummarized: "History summarized",
  VerificationQuestionsGenerated: "Verification questions",
  CoveContradictionDetected: "Contradiction detected",
};

export const EVENT_ACTIVITIES: Record<EventType, string> = {
  QuestionAsked: "Got your question",
  QuestionNormalized: "Rephrasing the question to understand it better",
  QuestionClassified: "Figuring out what kind of question this is",
  PlanCreated: "Drafting a search plan",
  PlanCritiqued: "Reviewing the plan before moving on",
  PlanRevised: "Rethinking the approach",
  HypothesesGenerated: "Generating competing hypotheses",
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
  QueryReformulated: "Refining the search terms",
  EchoChamberDetected: "Checking source diversity",
  RouteSelected: "Choosing a research lane",
  PlanGapsDetected: "Identifying missing angles",
  NoProgressDetected: "Confidence has plateaued",
  LaneEscalated: "Switching to deeper analysis",
  AgentThought: "Reasoning about the evidence",
  AgentAction: "Taking an action",
  AgentObservation: "Observing the results",
  HypothesisEvaluated: "Evaluating hypothesis",
  HistorySummarized: "Summarizing reasoning history",
  VerificationQuestionsGenerated: "Generating verification questions",
  CoveContradictionDetected: "Verifying the draft answer",
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
    case "QuestionClassified": {
      const qType = payload["detected_question_type"];
      const hint = payload["complexity_hint"];
      const qLabel =
        typeof qType === "string" && qType in QUESTION_TYPE_LABELS
          ? QUESTION_TYPE_LABELS[qType as QuestionType]
          : undefined;
      const cLabel =
        typeof hint === "string" && hint in COMPLEXITY_LABELS
          ? COMPLEXITY_LABELS[hint as ComplexityHint]
          : undefined;
      if (qLabel && cLabel) {
        return `Classified as ${qLabel} question — ${cLabel}`;
      }
      if (qLabel) {
        return `Classified as ${qLabel} question`;
      }
      if (cLabel) {
        return `Complexity: ${cLabel}`;
      }
      return getEventActivity(type);
    }
    case "PlanCreated":
    case "PlanRevised": {
      const hint = payload["complexity_hint"];
      const cLabel =
        typeof hint === "string" && hint in COMPLEXITY_LABELS
          ? COMPLEXITY_LABELS[hint as ComplexityHint]
          : undefined;
      const base =
        type === "PlanRevised"
          ? "Rethought the search plan"
          : "Drafted the search plan";
      return cLabel ? `${base} — ${cLabel.toLowerCase()}` : base;
    }
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
