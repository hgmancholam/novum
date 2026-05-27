/**
 * RunRow organism — one row in the history list.
 * See ui-prototype.md §3.2 (states L2/L3/L4) and BRD-12 §4.7.
 *
 * Presentational: no data fetching. Selection / hover handled via props + CSS.
 */

import { memo } from "react";

import { StatusBadge } from "@/components/molecules";
import { cn } from "@/lib/cn";
import { formatISO, formatRelative, truncate } from "@/lib/format";
import type { RunSummary } from "@/types/history";

export interface RunRowProps {
  run: RunSummary;
  isSelected: boolean;
  onSelect: (runId: string) => void;
}

const QUESTION_MAX = 60;

export const RunRow = memo(function RunRow({
  run,
  isSelected,
  onSelect,
}: RunRowProps) {
  const handleClick = (): void => {
    onSelect(run.id);
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      aria-current={isSelected ? "true" : undefined}
      data-testid="run-row"
      data-selected={isSelected ? "true" : "false"}
      className={cn(
        "w-full border-b border-[var(--glass-border)] px-3 py-3 text-left",
        "transition-colors duration-150 ease-out",
        "hover:bg-[var(--glass-bg)]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]",
        isSelected && "bg-[color-mix(in_srgb,var(--accent)_18%,transparent)]"
      )}
    >
      <p
        className={cn(
          "mb-0.5 text-sm font-medium",
          isSelected ? "text-[var(--text-primary)]" : "text-[var(--text-primary)]"
        )}
      >
        {truncate(run.question, QUESTION_MAX)}
      </p>
      <p className="mb-1.5 text-xs text-(--text-secondary)">
        {run.username}
      </p>
      <div className="flex items-center justify-between gap-2">
        <StatusBadge
          status={run.status}
          {...(run.stopReason !== null ? { stopReason: run.stopReason } : {})}
        />
        <time
          dateTime={run.startedAt}
          title={formatISO(run.startedAt)}
          className="text-xs text-[var(--text-secondary)]"
        >
          {formatRelative(run.startedAt)}
        </time>
      </div>
    </button>
  );
});
