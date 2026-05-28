/**
 * RunFeed organism — Claude-style live feed for the center panel.
 * IP-24 Phase 3.
 *
 * Consumes events via buildFeedSteps, renders molecules per step kind.
 * Sticky-bottom autoscroll (reusing IntersectionObserver pattern from TraceTimeline).
 * Collapse-after-completion with localStorage persistence.
 */

/* eslint-disable @typescript-eslint/no-unnecessary-condition */
/* WHY: defensive optional guards on event payload fields are intentional */

import { useEffect, useMemo, useRef, useState } from "react";
import {
  buildFeedSteps,
  type FeedStepData,
  type RunStreamEvent,
} from "@/lib/feedGrouping";
import {
  FeedStep,
  SearchStepCard,
  PlanStepCard,
  JudgeVerdictCard,
  type SearchSource,
  type SubClaim,
} from "@/components/molecules";
import { FeedRail, JumpToLatestPill, CollapseToggleButton } from "@/components/atoms";
import { FEED_TOGGLE_COLLAPSE, FEED_TOGGLE_EXPAND } from "@/lib/microcopy";
import { cn } from "@/lib/cn";

export interface RunFeedProps {
  events: readonly RunStreamEvent[];
  isComplete: boolean;
  className?: string | undefined;
}

const FEED_COLLAPSED_KEY = "novum_run_feed_collapsed";

function getInitialCollapsed(isComplete: boolean): boolean {
  if (!isComplete) return false;
  try {
    return localStorage.getItem(FEED_COLLAPSED_KEY) === "1";
  } catch {
    return true; // Default collapsed after completion
  }
}

function persistCollapsed(value: boolean): void {
  try {
    localStorage.setItem(FEED_COLLAPSED_KEY, value ? "1" : "0");
  } catch {
    // Ignore storage errors
  }
}

export function RunFeed({ events, isComplete, className }: RunFeedProps) {
  const steps = useMemo(
    () => buildFeedSteps(events as RunStreamEvent[], { isComplete }),
    [events, isComplete]
  );

  const [isCollapsed, setIsCollapsed] = useState(() =>
    getInitialCollapsed(isComplete)
  );
  const [sticky, setSticky] = useState(true);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Update collapsed state when completion changes
  useEffect(() => {
    if (isComplete) {
      setIsCollapsed(getInitialCollapsed(true));
    }
  }, [isComplete]);

  // Sticky-bottom observer
  useEffect(() => {
    const sentinel = bottomRef.current;
    if (!sentinel || typeof IntersectionObserver === "undefined") {
      setSticky(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry) {
          setSticky(entry.isIntersecting);
        }
      },
      { threshold: 0.5 }
    );

    observer.observe(sentinel);
    return () => { observer.disconnect(); };
  }, []);

  // Scroll to bottom when new events arrive and sticky
  useEffect(() => {
    if (sticky && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [events.length, sticky]);

  function handleJumpToLatest(): void {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }

  function toggleCollapsed(): void {
    const newValue = !isCollapsed;
    setIsCollapsed(newValue);
    persistCollapsed(newValue);
  }

  if (steps.length === 0) {
    return null;
  }

  // Calculate total duration - explicitly type as number for strictNullChecks compliance
  const lastEvent = events[events.length - 1];
  const firstEvent = events[0];
  const lastTimestamp: number = lastEvent?.timestamp_ms ?? 0;
  const firstTimestamp: number = firstEvent?.timestamp_ms ?? 0;
  const totalSeconds = events.length > 0
    ? Math.round((lastTimestamp - firstTimestamp) / 1000)
    : 0;

  return (
    <div
      ref={containerRef}
      data-testid="run-feed"
      className={cn("relative", className)}
    >
      {/* Collapse header (only after completion) */}
      {isComplete && events.length > 0 ? (
        <div className="sticky top-0 z-20 bg-[var(--bg-primary)] border-b border-[var(--glass-border)] px-4 py-2 flex items-center justify-between">
          <h3 className="text-sm font-medium text-[var(--text-secondary)]">
            Reasoning trace ({steps.length} steps · {totalSeconds}s)
          </h3>
          <CollapseToggleButton
            isCollapsed={isCollapsed}
            onToggle={toggleCollapsed}
            labelCollapse={FEED_TOGGLE_COLLAPSE}
            labelExpand={FEED_TOGGLE_EXPAND}
          />
        </div>
      ) : null}

      {/* Feed content */}
      {!isCollapsed ? (
        <div className="relative px-4 py-3">
          <FeedRail tone={isComplete ? "neutral" : "active"} />
          <ol className="flex flex-col relative">
            {steps.map((step, idx) => (
              <FeedStepRenderer
                key={`step-${idx.toString()}`}
                step={step}
                isLast={idx === steps.length - 1}
              />
            ))}
          </ol>
          <div ref={bottomRef} />
        </div>
      ) : null}

      {/* Jump to latest pill */}
      {!sticky && !isCollapsed ? (
        <div className="absolute bottom-4 right-4 z-10">
          <JumpToLatestPill onClick={handleJumpToLatest} />
        </div>
      ) : null}
    </div>
  );
}

interface FeedStepRendererProps {
  step: FeedStepData;
  isLast: boolean;
}

function FeedStepRenderer({ step, isLast }: FeedStepRendererProps) {
  switch (step.kind) {
    case "search": {
      const { query, sources } = step.payload as {
        query: string;
        sources: SearchSource[];
      };
      return (
        <SearchStepCard
          query={query}
          sources={sources}
          isActive={step.isActive}
          deltaMs={step.deltaMs}
        />
      );
    }
    case "plan": {
      const payload = step.payload;
      const rationale = (payload.rationale as string) ?? "";
      const subClaims = ((payload.sub_claims as unknown[]) ?? []).map(
        (c: unknown) => {
          const claim = c as Record<string, unknown>;
          return {
            id: (claim.id as string) ?? "",
            text: (claim.text as string) ?? "",
            status: (claim.status as SubClaim["status"]) ?? "pending",
          };
        }
      );
      const isRevision = payload.type === "PlanRevised";
      return (
        <PlanStepCard
          rationale={rationale}
          subClaims={subClaims}
          complexityHint={payload.complexity_hint as string | undefined}
          isActive={step.isActive}
          deltaMs={step.deltaMs}
          isRevision={isRevision}
        />
      );
    }
    case "judge": {
      const payload = step.payload;
      const passed = (payload.passed as boolean) ?? false;
      const finalConfidence = (payload.final_confidence as number) ?? 0;
      const threshold = (payload.threshold as number) ?? 0.7;
      const rationale = (payload.rationale as string) ?? "";
      return (
        <JudgeVerdictCard
          passed={passed}
          finalConfidence={finalConfidence}
          threshold={threshold}
          rationale={rationale}
          deltaMs={step.deltaMs}
        />
      );
    }
    case "done": {
      const stopReason = (step.payload.stop_reason as string) ?? "unknown";
      return (
        <FeedStep
          type="Stopped"
          title="Done"
          summary={`Stop reason: ${stopReason}`}
          isActive={step.isActive}
          deltaMs={step.deltaMs}
          isLast={isLast}
        />
      );
    }
    case "ambiguity": {
      return (
        <FeedStep
          type="AmbiguityDetected"
          title="Ambiguity detected"
          summary="The question has multiple interpretations"
          isActive={step.isActive}
          deltaMs={step.deltaMs}
          isLast={isLast}
        />
      );
    }
    case "contradiction": {
      return (
        <FeedStep
          type="ContradictionDetected"
          title="Contradiction spotted"
          summary="Sources disagree on key facts"
          isActive={step.isActive}
          deltaMs={step.deltaMs}
          isLast={isLast}
        />
      );
    }
    default: {
      // Generic fallback - use QuestionAsked as a safe default for unknown types
      return (
        <FeedStep
          type="QuestionAsked"
          title={(step.payload.type as string) ?? "Unknown event"}
          {...(step.isActive !== undefined ? { isActive: step.isActive } : {})}
          {...(step.deltaMs !== undefined ? { deltaMs: step.deltaMs } : {})}
          isLast={isLast}
        />
      );
    }
  }
}
