/**
 * Feed grouping logic — pure function for building feed steps from events.
 * IP-24 Phase 3.
 *
 * Algorithm:
 * - `ToolCalled` opens a search bucket.
 * - Consecutive `EvidenceAdded`, `SourceFailed`, `DeepFetchPerformed` with
 *   matching (or empty) `target_claim_id` get appended until interrupted.
 * - Interruption events: `PlanCreated`, `PlanRevised`, `JudgeRuled`,
 *   `ContradictionDetected`, `AmbiguityDetected`, `Stopped`, or a new
 *   `ToolCalled`.
 * - Other events map to their respective step kinds.
 */

/* eslint-disable @typescript-eslint/no-non-null-assertion */
/* WHY: array indexing in loops with bounds check is safe */

import type { RunStreamEvent } from "@/types/events";

export interface FeedStepData {
  kind:
    | "search"
    | "plan"
    | "judge"
    | "ambiguity"
    | "contradiction"
    | "done"
    | "generic";
  payload: Record<string, unknown>;
  deltaMs?: number | undefined;
  isActive?: boolean | undefined;
}

export type { RunStreamEvent };

interface BuildFeedStepsOptions {
  isComplete: boolean;
}

const INTERRUPTING_TYPES: ReadonlySet<string> = new Set([
  "PlanCreated",
  "PlanRevised",
  "JudgeRuled",
  "ContradictionDetected",
  "AmbiguityDetected",
  "Stopped",
]);

const GROUPABLE_EVIDENCE_TYPES: ReadonlySet<string> = new Set([
  "EvidenceAdded",
  "SourceFailed",
  "DeepFetchPerformed",
]);

// Resume events are lifecycle markers, not research steps — skip them in feed
const SKIPPABLE_TYPES: ReadonlySet<string> = new Set([
  "ResumedAfterCancel",
  "ResumedAfterError",
]);

function computeDelta(
  currentMs: number | undefined,
  prevMs: number | undefined
): number | undefined {
  if (currentMs === undefined || prevMs === undefined) return undefined;
  return currentMs - prevMs;
}

/** Helper to conditionally add deltaMs only when defined (exactOptionalPropertyTypes). */
function withDelta<T extends Omit<FeedStepData, "deltaMs">>(
  obj: T,
  delta: number | undefined
): T & { deltaMs?: number } {
  return delta !== undefined ? { ...obj, deltaMs: delta } : obj;
}

/**
 * Pure function: builds feed steps from raw events.
 */
export function buildFeedSteps(
  events: readonly RunStreamEvent[],
  options?: BuildFeedStepsOptions
): FeedStepData[] {
  const { isComplete = false } = options ?? {};
  const steps: FeedStepData[] = [];

  let currentBucket: {
    kind: "search";
    toolEvent: RunStreamEvent;
    children: RunStreamEvent[];
    claimId?: string;
  } | null = null;

  let prevTimestampMs: number | undefined = undefined;

  for (let i = 0; i < events.length; i++) {
    const event = events[i]!;
    const type = event.type;

    // Skip lifecycle markers (resume events)
    if (SKIPPABLE_TYPES.has(type)) {
      continue;
    }

    // Track timestamp for deltas
    if (event.timestamp_ms !== undefined) {
      prevTimestampMs = event.timestamp_ms;
    }

    // Check if this event closes an open search bucket
    if (currentBucket && INTERRUPTING_TYPES.has(type)) {
      // Close the search bucket
      steps.push(
        withDelta(
          {
            kind: "search",
            payload: {
              query: currentBucket.toolEvent.query ?? "",
              sources: currentBucket.children.map((e) => ({
                url: e.source_url ?? "",
                title: e.source_title ?? "",
                sourceType: e.source_type,
              })),
            },
          },
          computeDelta(
            currentBucket.toolEvent.timestamp_ms,
            prevTimestampMs
          )
        )
      );
      currentBucket = null;
    }

    // Handle ToolCalled — opens a new bucket (closes previous if any)
    if (type === "ToolCalled") {
      if (currentBucket) {
        // Close previous bucket
        steps.push(
          withDelta(
            {
              kind: "search",
              payload: {
                query: currentBucket.toolEvent.query ?? "",
                sources: currentBucket.children.map((e) => ({
                  url: e.source_url ?? "",
                  title: e.source_title ?? "",
                  sourceType: e.source_type,
                })),
              },
            },
            computeDelta(
              currentBucket.toolEvent.timestamp_ms,
              prevTimestampMs
            )
          )
        );
      }
      // Open new bucket
      const targetClaimId = event.target_claim_id as string | undefined;
      currentBucket = {
        kind: "search",
        toolEvent: event,
        children: [],
      };
      if (targetClaimId !== undefined) {
        currentBucket.claimId = targetClaimId;
      }
      continue;
    }

    // Check if this is evidence that can be grouped into current bucket
    if (currentBucket && GROUPABLE_EVIDENCE_TYPES.has(type)) {
      const eventClaimId = event.target_claim_id as string | undefined;
      // Append if claim IDs match or either is empty
      if (
        !currentBucket.claimId ||
        !eventClaimId ||
        currentBucket.claimId === eventClaimId
      ) {
        currentBucket.children.push(event);
        continue;
      }
    }

    // Otherwise, close any open bucket and process the event as standalone
    if (currentBucket) {
      steps.push(
        withDelta(
          {
            kind: "search",
            payload: {
              query: currentBucket.toolEvent.query ?? "",
              sources: currentBucket.children.map((e) => ({
                url: e.source_url ?? "",
                title: e.source_title ?? "",
                sourceType: e.source_type,
              })),
            },
          },
          computeDelta(
            currentBucket.toolEvent.timestamp_ms,
            prevTimestampMs
          )
        )
      );
      currentBucket = null;
    }

    // Map standalone event to step
    const stepKind = mapEventToStepKind(type);
    const stepPayload = { ...event };
    steps.push(
      withDelta(
        {
          kind: stepKind,
          payload: stepPayload,
        },
        computeDelta(
          event.timestamp_ms,
          prevTimestampMs
        )
      )
    );
  }

  // Close any remaining open bucket
  if (currentBucket) {
    steps.push(
      withDelta(
        {
          kind: "search",
          payload: {
            query: currentBucket.toolEvent.query ?? "",
            sources: currentBucket.children.map((e) => ({
              url: e.source_url ?? "",
              title: e.source_title ?? "",
              sourceType: e.source_type,
            })),
          },
        },
        computeDelta(
          currentBucket.toolEvent.timestamp_ms,
          prevTimestampMs
        )
      )
    );
  }

  // Mark last step as active if not complete
  if (!isComplete && steps.length > 0) {
    steps[steps.length - 1]!.isActive = true;
  }

  return steps;
}

function mapEventToStepKind(type: string): FeedStepData["kind"] {
  switch (type) {
    case "PlanCreated":
    case "PlanRevised":
      return "plan";
    case "JudgeRuled":
      return "judge";
    case "AmbiguityDetected":
      return "ambiguity";
    case "ContradictionDetected":
      return "contradiction";
    case "Stopped":
      return "done";
    default:
      return "generic";
  }
}
