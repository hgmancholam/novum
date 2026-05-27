/**
 * ResearchingBanner organism — C3 indicator while the run is in flight.
 * See ui-prototype.md §3.1 (C3) and BRD-13 §4.4.
 *
 * No data fetching. Pure presentational.
 */

import { GlassSurface, Spinner } from "@/components/atoms";
import { ElapsedClock } from "@/components/molecules";
import { cn } from "@/lib/cn";

export interface ResearchingBannerProps {
  /** ISO timestamp the run started — when provided, renders an elapsed clock. */
  startedAt?: string | undefined;
  className?: string | undefined;
  label?: string;
}

export function ResearchingBanner({
  startedAt,
  className,
  label = "Researching\u2026",
}: ResearchingBannerProps) {
  return (
    <GlassSurface
      role="status"
      aria-live="polite"
      data-testid="researching-banner"
      variant="subtle"
      elevation="sm"
      radius="md"
      className={cn(
        "mx-auto mt-6 flex w-full max-w-3xl items-center gap-3 px-4 py-3",
        "text-sm text-[var(--text-secondary)]",
        className
      )}
    >
      <Spinner size="sm" label={label} />
      <span className="flex-1">{label}</span>
      {startedAt !== undefined ? <ElapsedClock startedAt={startedAt} /> : null}
    </GlassSurface>
  );
}
