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
  className?: string;
}

export function TracePanel({ header, body, className }: TracePanelProps) {
  return (
    <GlassSurface
      data-testid="trace-panel"
      variant="default"
      elevation="lg"
      radius="none"
      className={cn("flex h-full w-full flex-col", className)}
    >
      {header !== undefined ? (
        <header className="border-b border-[var(--glass-border)] px-4 py-3">
          {header}
        </header>
      ) : null}
      <div
        role="log"
        aria-live="polite"
        aria-label="Event trace"
        className="flex-1 overflow-y-auto px-3 py-3"
      >
        {body}
      </div>
    </GlassSurface>
  );
}
