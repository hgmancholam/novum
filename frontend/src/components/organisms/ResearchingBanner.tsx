/**
 * ResearchingBanner organism — C3 indicator while the run is in flight.
 * See ui-prototype.md §3.1 (C3) and BRD-13 §4.4.
 *
 * No data fetching. Pure presentational.
 */

import { Spinner } from "@/components/atoms";
import { cn } from "@/lib/cn";

export interface ResearchingBannerProps {
  className?: string | undefined;
  label?: string;
}

export function ResearchingBanner({
  className,
  label = "Researching\u2026",
}: ResearchingBannerProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="researching-banner"
      className={cn(
        "mx-auto mt-6 flex w-full max-w-3xl items-center gap-3 rounded-[var(--radius-md)]",
        "border border-[var(--glass-border)] bg-[var(--glass-bg)] px-4 py-3",
        "text-sm text-[var(--text-secondary)]",
        className
      )}
    >
      <Spinner size="sm" label={label} />
      <span>{label}</span>
    </div>
  );
}
