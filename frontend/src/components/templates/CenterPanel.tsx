/**
 * CenterPanel template — geometry-only container for the center panel.
 * See ui-prototype.md §2 (layout) and §8.2 (templates).
 *
 * Slots: outcomeBar (optional 4px strip on terminal states), header, body.
 */

import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface CenterPanelProps {
  outcomeBar?: ReactNode;
  header?: ReactNode;
  body?: ReactNode;
  className?: string;
}

export function CenterPanel({
  outcomeBar,
  header,
  body,
  className,
}: CenterPanelProps) {
  return (
    <div
      data-testid="center-panel"
      className={cn(
        "flex h-full w-full flex-col bg-[var(--bg-primary)]",
        className
      )}
    >
      {outcomeBar !== undefined ? <div>{outcomeBar}</div> : null}
      {header !== undefined ? (
        <header className="border-b border-[var(--glass-border)] px-6 py-4">
          {header}
        </header>
      ) : null}
      <div className="flex-1 overflow-y-auto px-6 py-4">{body}</div>
    </div>
  );
}
