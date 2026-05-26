/**
 * ConfidenceBar molecule — single confidence value with optional label and threshold marker.
 * See ui-prototype.md §8.2 (molecules) and §1.3 (semantic tokens).
 */

import { cn } from "@/lib/cn";

export interface ConfidenceBarProps {
  /** 0–1 confidence value (clamped). */
  value: number;
  /** 0–1 threshold above which the bar reads as "passed". Defaults to 0.7. */
  threshold?: number;
  /** Hide the "Confidence / NN%" label row. */
  showLabel?: boolean;
  /** Optional override for the metric label (e.g. "Coverage"). */
  label?: string;
  className?: string;
}

function clamp01(n: number): number {
  if (Number.isNaN(n)) return 0;
  if (n < 0) return 0;
  if (n > 1) return 1;
  return n;
}

export function ConfidenceBar({
  value,
  threshold = 0.7,
  showLabel = true,
  label = "Confidence",
  className,
}: ConfidenceBarProps) {
  const v = clamp01(value);
  const t = clamp01(threshold);
  const percentage = Math.round(v * 100);
  const passed = v >= t;

  const labelId = `confidence-${label.toLowerCase().replace(/\s+/g, "-")}`;

  return (
    <div className={cn("w-full", className)}>
      {showLabel ? (
        <div className="mb-1 flex justify-between text-xs">
          <span id={labelId} className="text-[var(--text-secondary)]">
            {label}
          </span>
          <span
            data-passed={passed}
            className={cn(
              "font-medium tabular-nums",
              passed
                ? "text-[var(--semantic-success)]"
                : "text-[var(--semantic-warning)]"
            )}
          >
            {percentage}%
          </span>
        </div>
      ) : null}
      <div
        role="progressbar"
        aria-valuenow={percentage}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-labelledby={showLabel ? labelId : undefined}
        className="relative h-2 w-full overflow-hidden rounded-full bg-[var(--bg-tertiary)]"
      >
        <div
          data-testid="confidence-fill"
          data-passed={passed}
          className={cn(
            "h-full transition-[width] duration-200 ease-out",
            passed
              ? "bg-[var(--semantic-success)]"
              : "bg-[var(--semantic-warning)]"
          )}
          style={{ width: `${percentage}%` }}
        />
        <div
          data-testid="confidence-threshold"
          className="absolute top-0 h-full w-0.5 bg-[var(--text-secondary)] opacity-60"
          style={{ left: `${Math.round(t * 100)}%` }}
        />
      </div>
    </div>
  );
}
