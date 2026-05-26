/**
 * HistoryPanel template — geometry-only container for the left panel.
 * See ui-prototype.md §2 (layout) and §8.2 (templates).
 *
 * Slots: header, body, footer.
 * Glass background per §1.5 (visual effects).
 */

import type { ReactNode } from "react";
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
    <div
      data-testid="history-panel"
      className={cn(
        "flex h-full w-full flex-col bg-[var(--bg-secondary)] " +
          "backdrop-blur-[20px] backdrop-saturate-[180%]",
        className
      )}
    >
      {header !== undefined ? (
        <header className="border-b border-[var(--glass-border)] px-4 py-3">
          {header}
        </header>
      ) : null}
      <div className="flex-1 overflow-y-auto px-2 py-3">{body}</div>
      {footer !== undefined ? (
        <footer className="border-t border-[var(--glass-border)] px-4 py-3">
          {footer}
        </footer>
      ) : null}
    </div>
  );
}
