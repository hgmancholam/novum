/**
 * TraceTimeline organism — owns expansion state, sticky-bottom auto-scroll,
 * and renders the list of `EventNode`s.
 *
 * Data-only inputs:
 *   - `events`: ordered list of stream frames (RunStreamEvent shape).
 *   - `isComplete`: drives final-state behavior (sticky no longer needed).
 *
 * Sticky-bottom implementation:
 *   We attach a sentinel `<div ref={bottomRef}/>` after the last node and
 *   observe it with `IntersectionObserver`. While the sentinel is in view
 *   → sticky = true and new events scroll into view. When the user
 *   scrolls up the sentinel leaves view → sticky = false and the
 *   `JumpToLatestPill` appears.
 *
 *   The `IntersectionObserver` global is stubbed in tests via
 *   `installIntersectionObserverStub` (see `test-utils`). If the global
 *   is undefined we gracefully fall back to sticky = true.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import { JumpToLatestPill } from "@/components/atoms/JumpToLatestPill";
import { EventNode, type TraceEventInput } from "@/components/molecules/EventNode";
import { cn } from "@/lib/cn";
import { EXPANDED_BY_DEFAULT } from "@/lib/eventVisuals";
import type { ComplexityHint, EventType, QuestionDomain, QuestionType } from "@/types/events";
import { COMPLEXITY_LABELS, QUESTION_DOMAIN_LABELS, QUESTION_TYPE_LABELS } from "@/lib/eventLabels";

export interface TraceTimelineEvent {
  /** Optional uuid from the event log. */
  id?: string | null | undefined;
  /** Event type (may be a synthetic frame). */
  type: string;
  /** Optional step index from the payload. */
  step_index?: number | undefined;
  /** Optional unix-ms timestamp for delta computation. */
  timestamp_ms?: number | undefined;
  /** Anything else — rendered in the expanded payload viewer. */
  [key: string]: unknown;
}

export interface TraceTimelineProps {
  events: readonly TraceTimelineEvent[];
  isComplete: boolean;
  className?: string | undefined;
}

function keyOf(event: TraceTimelineEvent, index: number): string {
  return event.id !== null && event.id !== undefined && event.id !== ""
    ? `id:${event.id}`
    : `idx:${index.toString()}`;
}

function summaryOf(event: TraceTimelineEvent): string | undefined {
  const payload = event as Record<string, unknown>;

  if (event.type === "QuestionClassified") {
    const qType = payload["detected_question_type"];
    const hint = payload["complexity_hint"];
    const domainRaw = payload["domain"];
    const qLabel =
      typeof qType === "string" && qType in QUESTION_TYPE_LABELS
        ? QUESTION_TYPE_LABELS[qType as QuestionType]
        : undefined;
    const cLabel =
      typeof hint === "string" && hint in COMPLEXITY_LABELS
        ? COMPLEXITY_LABELS[hint as ComplexityHint]
        : undefined;
    const dLabel =
      typeof domainRaw === "string" &&
      domainRaw in QUESTION_DOMAIN_LABELS &&
      domainRaw !== "other"
        ? QUESTION_DOMAIN_LABELS[domainRaw as QuestionDomain]
        : undefined;
    const segs: string[] = [];
    if (cLabel) segs.push(cLabel);
    if (qLabel) segs.push(`${qLabel} question`);
    if (dLabel) segs.push(dLabel);
    if (segs.length > 0) return segs.join(" · ");
  }

  if (event.type === "PlanCreated" || event.type === "PlanRevised") {
    const hint = payload["complexity_hint"];
    const cLabel =
      typeof hint === "string" && hint in COMPLEXITY_LABELS
        ? COMPLEXITY_LABELS[hint as ComplexityHint]
        : undefined;
    if (cLabel) return cLabel;
  }

  const candidates = [
    "summary",
    "normalized_question",
    "question",
    "answer",
    "claim",
    "verdict",
    "reason",
    "tool",
    "source",
  ];
  for (const k of candidates) {
    const v = payload[k];
    if (typeof v === "string" && v.length > 0) {
      return v.length > 120 ? `${v.slice(0, 117)}…` : v;
    }
  }
  return undefined;
}

export function TraceTimeline({
  events,
  isComplete,
  className,
}: TraceTimelineProps) {
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(
    () => new Set()
  );
  const [sticky, setSticky] = useState(true);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const items = useMemo<TraceEventInput[]>(() => {
    let prevTs: number | undefined;
    return events.map((evt, idx) => {
      const ts = typeof evt.timestamp_ms === "number" ? evt.timestamp_ms : undefined;
      const deltaMs =
        ts !== undefined && prevTs !== undefined ? ts - prevTs : undefined;
      if (ts !== undefined) {
        prevTs = ts;
      }
      const input: TraceEventInput = {
        key: keyOf(evt, idx),
        type: evt.type,
        payload: evt,
        ...(typeof evt.step_index === "number"
          ? { stepIndex: evt.step_index }
          : {}),
        ...(deltaMs !== undefined ? { deltaMs } : {}),
      };
      const summary = summaryOf(evt);
      if (summary !== undefined) {
        input.summary = summary;
      }
      return input;
    });
  }, [events]);

  // Seed `JudgeRuled` events into the expanded set as they arrive.
  useEffect(() => {
    setExpandedKeys((prev) => {
      let mutated = false;
      const next = new Set(prev);
      for (const it of items) {
        if (
          EXPANDED_BY_DEFAULT.has(it.type as EventType) &&
          !next.has(it.key)
        ) {
          next.add(it.key);
          mutated = true;
        }
      }
      return mutated ? next : prev;
    });
  }, [items]);

  // IntersectionObserver on the bottom sentinel.
  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const IOctor = window.IntersectionObserver;
    if (typeof IOctor !== "function") {
      setSticky(true);
      return;
    }
    const node = bottomRef.current;
    if (node === null) {
      return;
    }
    const root = containerRef.current;
    const options: IntersectionObserverInit = root !== null ? { root } : {};
    const observer = new IOctor((entries) => {
      const entry = entries[0];
      if (entry !== undefined) {
        setSticky(entry.isIntersecting);
      }
    }, options);
    observer.observe(node);
    return () => {
      observer.disconnect();
    };
  }, []);

  // When sticky AND not yet complete AND new events arrive → scroll to bottom.
  useEffect(() => {
    if (!sticky) {
      return;
    }
    const node = bottomRef.current;
    if (node === null) {
      return;
    }
    if (typeof node.scrollIntoView === "function") {
      node.scrollIntoView({ block: "end" });
    }
  }, [items.length, sticky]);

  const toggle = (key: string): void => {
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const handleJumpToLatest = (): void => {
    const node = bottomRef.current;
    if (node !== null && typeof node.scrollIntoView === "function") {
      node.scrollIntoView({ block: "end", behavior: "smooth" });
    }
    setSticky(true);
  };

  return (
    <div
      ref={containerRef}
      data-testid="trace-timeline"
      data-sticky={sticky}
      data-complete={isComplete}
      className={cn("relative flex h-full flex-col gap-3", className)}
    >
      <ol className="flex flex-col gap-2" data-testid="trace-timeline-list">
        {items.map((item) => (
          <EventNode
            key={item.key}
            event={item}
            expanded={expandedKeys.has(item.key)}
            onToggle={toggle}
            forkSlot={null}
          />
        ))}
      </ol>
      <div
        ref={bottomRef}
        data-testid="trace-timeline-sentinel"
        aria-hidden="true"
        className="scroll-mb-32"
      />
      {!sticky && !isComplete ? (
        <div className="pointer-events-none sticky bottom-2 flex justify-center">
          <div className="pointer-events-auto">
            <JumpToLatestPill onClick={handleJumpToLatest} />
          </div>
        </div>
      ) : null}
    </div>
  );
}
