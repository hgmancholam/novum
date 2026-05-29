/**
 * EventNode molecule — one row in the trace timeline.
 *
 * - Compact (default): icon + type + 1-line summary · meta (step + Δt ms).
 * - Expanded: same header + EventPayloadViewer beneath.
 *
 * `forkSlot` is a reserved top-right region. The actual fork button ships
 * in BRD-15; this iter renders the slot only when something is passed in.
 *
 * IP-22: special rendering for PriorRunHintReplayed events with clickable
 * navigation to source run (BRD-22, US-22-4).
 */

import { type ReactNode } from "react";
import { Recycle } from "lucide-react";

import { EventIcon } from "@/components/atoms/EventIcon";
import { EventPayloadViewer } from "@/components/atoms/EventPayloadViewer";
import { cn } from "@/lib/cn";
import { getEventLabel } from "@/lib/eventLabels";
import { isDecisionEvent } from "@/lib/eventVisuals";
import { useSelectionStore } from "@/stores/selectionStore";

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

/**
 * Format a relative time string from an ISO 8601 timestamp.
 * Used for PriorRunHintReplayed events (IP-22).
 */
function formatRelativeTime(isoTimestamp: string): string {
  const date = new Date(isoTimestamp);
  const now = Date.now();
  const diffMs = now - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

  if (diffDays > 0) {
    return rtf.format(-diffDays, "day");
  }
  if (diffHours > 0) {
    return rtf.format(-diffHours, "hour");
  }
  if (diffMinutes > 0) {
    return rtf.format(-diffMinutes, "minute");
  }
  return rtf.format(-diffSeconds, "second");
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
  const setSelectedRunId = useSelectionStore((state) => state.setSelectedRunId);

  // IP-22: Special rendering for PriorRunHintReplayed events
  if (event.type === "PriorRunHintReplayed") {
    const payload = event.payload as {
      source_run_id?: string;
      source_final_confidence?: number;
      prior_completed_at?: string;
    };
    const relative = payload.prior_completed_at
      ? formatRelativeTime(payload.prior_completed_at)
      : "recently";
    const confidence = payload.source_final_confidence?.toFixed(2) ?? "?";
    const label = `Same question answered ${relative}. Reused that result (confidence ${confidence}).`;
    return (
      <li
        data-testid="event-node"
        data-event-type={event.type}
        data-expanded={expanded}
        data-decision={false}
        className={cn(
          "rounded-[var(--radius-sm)] border border-[var(--glass-border)]",
          "bg-[var(--bg-tertiary)] p-2 text-xs",
          expanded ? "shadow-sm" : "",
          className
        )}
      >
        <button
          type="button"
          role="link"
          onClick={(e) => {
            if (e.shiftKey || e.ctrlKey || e.metaKey) {
              onToggle(event.key);
            } else if (payload.source_run_id !== undefined) {
              setSelectedRunId(payload.source_run_id);
            }
          }}
          aria-label={label}
          className={cn(
            "flex w-full items-start gap-2 text-left",
            "hover:bg-[var(--glass-border)] transition-colors cursor-pointer"
          )}
        >
          <Recycle
            aria-hidden="true"
            width={14}
            height={14}
            className="mt-0.5 shrink-0 text-[var(--accent)]"
          />
          <span className="flex-1 min-w-0">
            <span className="flex items-baseline justify-between gap-2">
              <span className="font-medium text-[var(--text-primary)]">
                {getEventLabel(event.type)}
              </span>
              {meta !== null ? (
                <span className="shrink-0 text-[var(--text-muted)]">{meta}</span>
              ) : null}
            </span>
            <span className="mt-0.5 block text-[var(--text-secondary)]">
              {label}
            </span>
          </span>
        </button>
        {expanded ? (
          <div className="mt-2 border-t border-[var(--glass-border)] pt-2">
            <EventPayloadViewer value={event.payload} />
          </div>
        ) : null}
      </li>
    );
  }

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
          <span className="flex items-baseline justify-between gap-2">
            <span className="font-medium text-[var(--text-primary)]">
              {getEventLabel(event.type)}
            </span>
            {meta !== null ? (
              <span className="shrink-0 text-[var(--text-muted)]">{meta}</span>
            ) : null}
          </span>
          {event.summary !== undefined && event.summary !== "" ? (
            <span className="mt-0.5 block text-[var(--text-secondary)]">
              {event.summary}
            </span>
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
