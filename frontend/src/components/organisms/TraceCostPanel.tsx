/**
 * TraceCostPanel organism — T1d "Trace · Cost" panel body (BRD-29 §4.7).
 *
 * Pure presentational: receives totals + rows from a page-level container
 * (data fetching belongs to `pages/` per the Atomic Design enforcement in
 * `eslint.config.js`).
 */

import { GlassSurface } from "@/components/atoms";
import { CostBreakdownBar, CostBreakdownTable } from "@/components/molecules";
import { cn } from "@/lib/cn";
import { formatTokens, formatUsd } from "@/lib/formatCost";
import type { ProviderCostRow } from "@/types/costs";

export interface TraceCostPanelProps {
  totalUsd: number;
  totalPromptTokens: number;
  totalCompletionTokens: number;
  rows: readonly ProviderCostRow[];
  isLoading?: boolean;
  isError?: boolean;
  onRetry?: () => void;
  className?: string;
}

export function TraceCostPanel({
  totalUsd,
  totalPromptTokens,
  totalCompletionTokens,
  rows,
  isLoading = false,
  isError = false,
  onRetry,
  className,
}: TraceCostPanelProps) {
  if (isLoading) {
    return (
      <div
        data-testid="trace-cost-panel-loading"
        className={cn(
          "flex flex-col gap-3 p-4 text-xs text-[var(--text-muted)]",
          className
        )}
      >
        <div className="h-3 w-24 animate-pulse rounded bg-[var(--glass-bg)]" />
        <div className="h-2 w-full animate-pulse rounded-full bg-[var(--glass-bg)]" />
        <div className="h-24 w-full animate-pulse rounded bg-[var(--glass-bg)]" />
      </div>
    );
  }

  if (isError) {
    return (
      <div
        data-testid="trace-cost-panel-error"
        className={cn(
          "flex flex-col items-center gap-2 p-6 text-center text-xs text-[var(--text-muted)]",
          className
        )}
      >
        <p>Failed to load cost breakdown.</p>
        {onRetry !== undefined ? (
          <button
            type="button"
            onClick={onRetry}
            className="rounded-md border border-[var(--glass-border)] px-2 py-1 text-[var(--text-primary)] hover:bg-[var(--glass-bg)]"
          >
            Retry
          </button>
        ) : null}
      </div>
    );
  }

  const totalTokens = totalPromptTokens + totalCompletionTokens;

  return (
    <GlassSurface
      data-testid="trace-cost-panel"
      variant="subtle"
      elevation="none"
      radius="md"
      className={cn("flex flex-col gap-4 p-4", className)}
    >
      <header className="flex items-baseline justify-between">
        <h3 className="text-sm font-medium text-[var(--text-primary)]">
          Cost breakdown
        </h3>
        <span className="font-mono text-base text-[var(--accent)]">
          {formatUsd(totalUsd)}
          <span className="ml-2 text-xs text-[var(--text-muted)]">
            {formatTokens(totalTokens)} tok
          </span>
        </span>
      </header>
      <CostBreakdownBar rows={rows} />
      <CostBreakdownTable rows={rows} />
    </GlassSurface>
  );
}
