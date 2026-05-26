/**
 * StatusBadge molecule — renders run status / stop_reason as a labeled Badge.
 * Microcopy and color mapping per ui-prototype.md §3.2 / §7 and requirement-understanding.md (RF-02).
 */

import { Badge, type BadgeVariant } from "@/components/atoms";
import type { StopReason } from "@/types/events";

export type RunStatus = "running" | "completed" | "stopped";

export interface StatusBadgeProps {
  status: RunStatus;
  stopReason?: StopReason;
  className?: string;
}

const stopReasonLabels: Record<StopReason, string> = {
  judge_confirmed: "Confirmed",
  honest_unanswerable: "Unanswerable",
  honest_contradiction: "Contradiction",
  honest_ambiguous: "Ambiguous",
  stopped_by_budget: "Budget reached",
  user_cancelled: "Cancelled",
  errored: "Error",
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
  className,
}: StatusBadgeProps) {
  if (status === "running") {
    return (
      <Badge variant="info" className={className}>
        Running
      </Badge>
    );
  }

  if (stopReason !== undefined) {
    return (
      <Badge variant={stopReasonVariants[stopReason]} className={className}>
        {stopReasonLabels[stopReason]}
      </Badge>
    );
  }

  return (
    <Badge variant="default" className={className}>
      Unknown
    </Badge>
  );
}
