/**
 * HistoryPanel template — geometry-only container for the left panel.
 * See ui-prototype.md §2 (layout), §8.2 (templates) and ui-design.md §2.3.
 *
 * Slots: header, body, footer.
 * Glass background per ui-design.md §2.3.
 */

import type { ReactNode } from "react";
import { GlassSurface } from "@/components/atoms";
import { cn } from "@/lib/cn";

export interface HistoryPanelProps {
  header?: ReactNode;
  body?: ReactNode;
  footer?: ReactNode;
  className?: string;
}

export function HistoryPanel({
  header,
  body,
  footer,
  className,
}: HistoryPanelProps) {
  return (
    <GlassSurface
      data-testid="history-panel"
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
      <div className="flex-1 overflow-y-auto px-2 py-3 pb-12">{body}</div>
      {footer !== undefined ? (
        <footer className="border-t border-[var(--glass-border)] px-4 py-3">
          {footer}
        </footer>
      ) : null}
    </GlassSurface>
  );
}
