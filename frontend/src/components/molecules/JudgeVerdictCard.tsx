/**
 * JudgeVerdictCard molecule — display for JudgeRuled events.
 * IP-24 Phase 2.
 */

import { CheckCircle2, XCircle } from "lucide-react";
import { FeedStep } from "./FeedStep";
import { Badge } from "@/components/atoms";
import { cn } from "@/lib/cn";

export interface JudgeVerdictCardProps {
  passed: boolean;
  finalConfidence: number;
  threshold: number;
  rationale: string;
  deltaMs?: number | undefined;
  className?: string | undefined;
}

export function JudgeVerdictCard({
  passed,
  finalConfidence,
  threshold,
  rationale,
  deltaMs,
  className,
}: JudgeVerdictCardProps) {
  const percentage = Math.round(finalConfidence * 100);
  const thresholdPercentage = Math.round(threshold * 100);

  return (
    <FeedStep
      type="JudgeRuled"
      title="Judge verdict"
      deltaMs={deltaMs}
      className={className}
    >
      <div className="flex items-center gap-2 mb-3">
        <Badge
          variant={passed ? "success" : "warning"}
          className="text-xs inline-flex items-center gap-1"
        >
          {passed ? (
            <CheckCircle2 aria-hidden="true" width={12} height={12} />
          ) : (
            <XCircle aria-hidden="true" width={12} height={12} />
          )}
          {passed ? "Confirmed" : "Retry suggested"}
        </Badge>
        <span className="text-xs text-[var(--text-muted)]">
          {percentage.toString()}% (threshold: {thresholdPercentage.toString()}%)
        </span>
      </div>

      {/* Confidence bar */}
      <div className="mb-3">
        <div
          role="progressbar"
          aria-valuenow={percentage}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Final confidence"
          className="relative h-2 w-full overflow-hidden rounded-full bg-[var(--bg-tertiary)]"
        >
          <div
            data-testid="confidence-fill"
            className={cn(
              "h-full transition-[width] duration-200 ease-out",
              passed
                ? "bg-[var(--semantic-success)]"
                : "bg-[var(--semantic-warning)]"
            )}
            style={{ width: `${percentage.toString()}%` }}
          />
          {/* Threshold marker */}
          <div
            className="absolute top-0 bottom-0 w-px bg-[var(--text-muted)]"
            style={{ left: `${thresholdPercentage.toString()}%` }}
            aria-hidden="true"
          />
        </div>
      </div>

      {/* Rationale (always expanded per IP-24) */}
      <div>
        <span className="text-xs text-[var(--text-muted)] block mb-1">
          Rationale
        </span>
        <p className="text-sm text-[var(--text-secondary)]">{rationale}</p>
      </div>
    </FeedStep>
  );
}
