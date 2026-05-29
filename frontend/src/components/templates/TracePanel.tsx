/**
 * TracePanel template — geometry-only container for the right panel.
 * See ui-prototype.md §2 (layout), §8.2 (templates), §1.8 (a11y) and
 * ui-design.md §2.3 (glass surfaces).
 *
 * Slots: header, body.
 * The body region carries role="log" + aria-live="polite" per §1.8.
 */

import type { ReactNode } from "react";
import { GlassSurface } from "@/components/atoms";
import { cn } from "@/lib/cn";

export interface TracePanelProps {
  header?: ReactNode;
  body?: ReactNode;
  /** When true, padding shrinks so the header fits inside the 40px collapsed rail. */
  isCollapsed?: boolean;
  className?: string;
}

export function TracePanel({ header, body, isCollapsed = false, className }: TracePanelProps) {
  return (
    <GlassSurface
      data-testid="trace-panel"
      variant="default"
      elevation="lg"
      radius="none"
      className={cn("flex h-full w-full flex-col", className)}
    >
      {header !== undefined ? (
        <header
          className={cn(
            "border-b border-[var(--glass-border)]",
            isCollapsed ? "px-1 py-2" : "px-4 py-3",
          )}
        >
          {header}
        </header>
      ) : null}
      <div
        role="log"
        aria-live="polite"
        aria-label="Event trace"
        className={cn(
          "flex-1 overflow-y-auto pb-20",
          isCollapsed ? "p-0" : "px-3 py-3",
        )}
      >
        {body}
      </div>
    </GlassSurface>
  );
}
