/**
 * TraceCostPanelContainer — page-level data owner for the T1d "Cost" tab.
 *
 * Per `eslint.config.js`, only `pages/` may call `useRun*` hooks. This
 * container reads from the same TanStack-Query cache that
 * `CenterPanelContainer` keeps in sync via the SSE stream, so the cost
 * data shown here matches the live-updating header chip.
 */

import { TraceCostPanel } from "@/components/organisms";
import { useRunCosts } from "@/hooks/useRunCosts";

export interface TraceCostPanelContainerProps {
  runId: string;
}

export function TraceCostPanelContainer({
  runId,
}: TraceCostPanelContainerProps) {
  const { total, rows, isLoading, isError, refetch } = useRunCosts(runId);

  return (
    <TraceCostPanel
      totalUsd={total.usd}
      totalPromptTokens={total.promptTokens}
      totalCompletionTokens={total.completionTokens}
      rows={rows}
      isLoading={isLoading}
      isError={isError}
      onRetry={refetch}
    />
  );
}
