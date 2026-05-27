/**
 * EventNode molecule — one row in the trace timeline.
 *
 * - Compact (default): icon + type + 1-line summary · meta (step + Δt ms).
 * - Expanded: same header + EventPayloadViewer beneath.
 *
 * `forkSlot` is a reserved top-right region. The actual fork button ships
 * in BRD-15; this iter renders the slot only when something is passed in.
 */

import { type ReactNode } from "react";

import { EventIcon } from "@/components/atoms/EventIcon";
import { EventPayloadViewer } from "@/components/atoms/EventPayloadViewer";
import { cn } from "@/lib/cn";
import { getEventLabel } from "@/lib/eventLabels";
import { isDecisionEvent } from "@/lib/eventVisuals";

export interface TraceEventInput {
  /** Stable key — `event.id` when present, otherwise an "idx:N" string. */
  key: string;
  /** Event type as reported by SSE (may not be in EventType union). */
  type: string;
  /** 1-based step index, when known. */
  stepIndex?: number | undefined;
  /** Optional time-delta from the previous event in ms. */
  deltaMs?: number | undefined;
  /** Full payload (for the expanded view). */
  payload: unknown;
  /** One-line summary derived from the payload. */
  summary?: string | undefined;
}

export interface EventNodeProps {
  event: TraceEventInput;
  expanded: boolean;
  onToggle: (key: string) => void;
  /** BRD-15 slot — render `null` in V1. */
  forkSlot?: ReactNode;
  className?: string | undefined;
}

function metaLine(stepIndex?: number, deltaMs?: number): string | null {
  const parts: string[] = [];
  if (typeof stepIndex === "number") {
    parts.push(`step ${stepIndex.toString()}`);
  }
  if (typeof deltaMs === "number") {
    parts.push(`Δ ${deltaMs.toString()} ms`);
  }
  return parts.length > 0 ? parts.join(" · ") : null;
}

export function EventNode({
  event,
  expanded,
  onToggle,
  forkSlot,
  className,
}: EventNodeProps) {
  const meta = metaLine(event.stepIndex, event.deltaMs);
  const decision = isDecisionEvent(event.type);

  return (
    <li
      data-testid="event-node"
      data-event-type={event.type}
      data-expanded={expanded}
      data-decision={decision}
      className={cn(
        "rounded-[var(--radius-sm)] border border-[var(--glass-border)]",
        "bg-[var(--bg-tertiary)] p-2 text-xs",
        expanded ? "shadow-sm" : "",
        className
      )}
    >
      <button
        type="button"
        onClick={() => {
          onToggle(event.key);
        }}
        aria-expanded={expanded}
        aria-label={`${expanded ? "Collapse" : "Expand"} ${event.type}`}
        className="flex w-full items-start gap-2 text-left"
      >
        <EventIcon type={event.type} />
        <span className="flex-1 min-w-0">
          <span className="flex items-center gap-2">
            <span className="font-medium text-[var(--text-primary)]">
              {getEventLabel(event.type)}
            </span>
            {event.summary !== undefined && event.summary !== "" ? (
              <span className="truncate text-[var(--text-secondary)]">
                · {event.summary}
              </span>
            ) : null}
          </span>
          {meta !== null ? (
            <span className="block text-[var(--text-muted)]">{meta}</span>
          ) : null}
        </span>
        {forkSlot !== undefined && forkSlot !== null ? (
          <span
            data-testid="event-fork-slot"
            onClick={(e) => {
              e.stopPropagation();
            }}
            className="shrink-0"
          >
            {forkSlot}
          </span>
        ) : null}
      </button>
      {expanded ? (
        <div className="mt-2 border-t border-[var(--glass-border)] pt-2">
          <EventPayloadViewer value={event.payload} />
        </div>
      ) : null}
    </li>
  );
}
