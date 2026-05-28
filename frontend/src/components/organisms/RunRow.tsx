/**
 * RunRow organism — one row in the history list.
 * See ui-prototype.md §3.2 (states L2/L3/L4) and BRD-12 §4.7.
 *
 * Presentational: no data fetching. Selection / hover handled via props + CSS.
 */

import { memo } from "react";

import { StatusDot } from "@/components/molecules";
import { ProviderIcon } from "@/components/atoms";
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
        "relative w-full border-b border-[var(--glass-border)] px-3 py-3 pr-7 text-left",
        "transition-colors duration-150 ease-out",
        "hover:bg-[var(--glass-bg)]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]",
        isSelected && "bg-[color-mix(in_srgb,var(--accent)_18%,transparent)]"
      )}
    >
      <StatusDot
        status={run.status}
        {...(run.stopReason !== null ? { stopReason: run.stopReason } : {})}
        className="absolute right-3 top-3"
      />
      <ProviderIcon
        name={run.llmProvider}
        size="xs"
        className="absolute right-3 top-8"
      />
      <p className="mb-1 text-sm font-medium text-(--text-primary)">
        {truncate(run.question, QUESTION_MAX)}
      </p>
      <p className="text-xs text-(--text-muted)">
        <span>{run.username}</span>
        <span aria-hidden="true" className="mx-1.5 text-(--text-muted)">·</span>
        <time dateTime={run.startedAt} title={formatISO(run.startedAt)}>
          {formatRelative(run.startedAt)}
        </time>
      </p>
    </button>
  );
});
