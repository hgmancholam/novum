/**
 * TraceHeader organism — title + event count + live indicator dot + collapse toggle (IP-24).
 * Pure presentational; container computes `isStreaming` from
 * `isConnected && !isComplete`.
 */

import { cn } from "@/lib/cn";
import { CollapseToggleButton } from "@/components/atoms";
import { TRACE_PANEL_COLLAPSE, TRACE_PANEL_EXPAND } from "@/lib/microcopy";

export interface TraceHeaderProps {
  eventCount: number;
  isStreaming: boolean;
  /** IP-24 Phase 5: Collapse state. */
  isCollapsed?: boolean;
  /** IP-24 Phase 5: Collapse toggle handler. */
  onToggleCollapse?: (() => void) | undefined;
  className?: string | undefined;
}

export function TraceHeader({
  eventCount,
  isStreaming,
  isCollapsed = false,
  onToggleCollapse,
  className,
}: TraceHeaderProps) {
  return (
    <div
      data-testid="trace-header"
      className={cn(
        "flex items-center gap-2",
        isCollapsed ? "justify-center" : "justify-between",
        className,
      )}
    >
      {!isCollapsed ? (
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
      ) : null}
      <div className="flex items-center gap-2">
        {isStreaming && !isCollapsed ? (
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
        {onToggleCollapse !== undefined ? (
          <CollapseToggleButton
            isCollapsed={isCollapsed}
            onToggle={onToggleCollapse}
            labelCollapse={TRACE_PANEL_COLLAPSE}
            labelExpand={TRACE_PANEL_EXPAND}
          />
        ) : null}
      </div>
    </div>
  );
}
