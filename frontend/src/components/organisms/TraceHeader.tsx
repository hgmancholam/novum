/**
 * TraceHeader organism — title + event count + live indicator dot.
 * Pure presentational; container computes `isStreaming` from
 * `isConnected && !isComplete`.
 */

import { cn } from "@/lib/cn";

export interface TraceHeaderProps {
  eventCount: number;
  isStreaming: boolean;
  className?: string | undefined;
}

export function TraceHeader({
  eventCount,
  isStreaming,
  className,
}: TraceHeaderProps) {
  return (
    <div
      data-testid="trace-header"
      className={cn("flex items-center justify-between gap-2", className)}
    >
      <div className="flex flex-col">
        <h2 className="text-sm font-medium text-[var(--text-primary)]">Trace</h2>
        <span className="text-[10px] text-[var(--text-muted)]">
          {eventCount === 0
            ? "no events yet"
            : eventCount === 1
              ? "1 event"
              : `${eventCount.toString()} events`}
        </span>
      </div>
      {isStreaming ? (
        <span
          data-testid="trace-live-indicator"
          className="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-wide"
          style={{ color: "var(--semantic-success)" }}
        >
          <span
            aria-hidden="true"
            className="inline-block h-1.5 w-1.5 animate-pulse rounded-full"
            style={{ backgroundColor: "var(--semantic-success)" }}
          />
          Live
        </span>
      ) : null}
    </div>
  );
}
