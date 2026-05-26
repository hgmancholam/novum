/**
 * StatusBadge molecule — renders run status / stop_reason as a labeled Badge.
 * Microcopy and color mapping per ui-prototype.md §7.4 and §3.2 (RF-02).
 */

import { Badge, type BadgeVariant } from "@/components/atoms";
import type { StopReason } from "@/types/events";

export type RunStatus = "running" | "completed" | "stopped";

export interface StatusBadgeProps {
  status: RunStatus;
  stopReason?: StopReason;
  /** Optional failure reason shown after "Errored —" when stopReason === "errored". */
  errorReason?: string;
  className?: string;
}

const stopReasonLabels: Record<StopReason, string> = {
  judge_confirmed: "Judge confirmed",
  honest_unanswerable: "Honest stop — unanswerable",
  honest_contradiction: "Honest stop — contradiction",
  honest_ambiguous: "Honest stop — ambiguous",
  stopped_by_budget: "Stopped on budget",
  user_cancelled: "Cancelled",
  errored: "Errored",
};

const stopReasonVariants: Record<StopReason, BadgeVariant> = {
  judge_confirmed: "success",
  honest_unanswerable: "warning",
  honest_contradiction: "warning",
  honest_ambiguous: "warning",
  stopped_by_budget: "warning",
  user_cancelled: "secondary",
  errored: "error",
};

export function StatusBadge({
  status,
  stopReason,
  errorReason,
  className,
}: StatusBadgeProps) {
  if (status === "running") {
    return (
      <Badge variant="info" className={className}>
        Researching…
      </Badge>
    );
  }

  if (stopReason !== undefined) {
    const baseLabel = stopReasonLabels[stopReason];
    const label =
      stopReason === "errored" && errorReason !== undefined && errorReason !== ""
        ? `${baseLabel} — ${errorReason}`
        : baseLabel;
    return (
      <Badge variant={stopReasonVariants[stopReason]} className={className}>
        {label}
      </Badge>
    );
  }

  return (
    <Badge variant="default" className={className}>
      Unknown
    </Badge>
  );
}
