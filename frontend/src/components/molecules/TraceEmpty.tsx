/**
 * TraceEmpty molecule — T1a state for HomePage. Verbatim microcopy from
 * ui-prototype.md §7 / §3.3.
 */

import { cn } from "@/lib/cn";

export interface TraceEmptyProps {
  className?: string | undefined;
}

export const TRACE_EMPTY_MESSAGE = "Trace will appear here when research starts.";

export function TraceEmpty({ className }: TraceEmptyProps) {
  return (
    <p
      data-testid="trace-empty"
      className={cn(
        "text-xs text-[var(--text-secondary)]",
        className
      )}
    >
      {TRACE_EMPTY_MESSAGE}
    </p>
  );
}
