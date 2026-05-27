/**
 * OutcomeBar atom — 4 px colored strip at the top of `CenterPanel` on terminal
 * states (C6–C10). Pre-attentive recognition of stop_reason variant.
 * See ui-prototype.md §3.2.5.
 */

import { cn } from "@/lib/cn";
import type { StopReason } from "@/types/events";

export type OutcomeVariant = "success" | "warning" | "error" | "neutral";

const reasonToVariant: Record<StopReason, OutcomeVariant> = {
  judge_confirmed: "success",
  stopped_by_budget: "warning",
  user_cancelled: "neutral",
  errored: "error",
};

const variantToken: Record<OutcomeVariant, string> = {
  success: "var(--semantic-success)",
  warning: "var(--semantic-warning)",
  error: "var(--semantic-danger)",
  neutral: "var(--semantic-neutral)",
};

export interface OutcomeBarProps {
  /** When provided, color is derived from the stop_reason. */
  reason?: StopReason | undefined;
  /** Explicit variant override. Ignored when `reason` is provided. */
  variant?: OutcomeVariant | undefined;
  className?: string | undefined;
}

export function OutcomeBar({ reason, variant, className }: OutcomeBarProps) {
  const v: OutcomeVariant =
    reason !== undefined ? reasonToVariant[reason] : (variant ?? "neutral");
  return (
    <div
      role="presentation"
      aria-hidden="true"
      data-testid="outcome-bar"
      data-variant={v}
      className={cn("h-1 w-full", className)}
      style={{ backgroundColor: variantToken[v] }}
    />
  );
}
