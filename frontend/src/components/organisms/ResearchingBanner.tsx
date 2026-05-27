/**
 * ResearchingBanner organism — C3 indicator while the run is in flight.
 * See ui-prototype.md §3.1 (C3) and BRD-13 §4.4.
 *
 * Renders a two-line live indicator:
 *   line 1 — bouncing dots + current activity + elapsed clock
 *   line 2 — "step N · X events" meta
 *
 * The activity text is derived from the latest emitted event so the user
 * knows what the agent is doing without sending another request.
 *
 * Pure presentational.
 */

import { AnimatedDots, GlassSurface } from "@/components/atoms";
import { ElapsedClock } from "@/components/molecules";
import { cn } from "@/lib/cn";
import { getEventActivity } from "@/lib/eventLabels";

export interface ResearchingBannerLatestEvent {
  type: string;
  step_index?: number | undefined;
}

export interface ResearchingBannerProps {
  /** ISO timestamp the run started — when provided, renders an elapsed clock. */
  startedAt?: string | undefined;
  /** Most recent event emitted by the agent; drives the activity copy. */
  latestEvent?: ResearchingBannerLatestEvent | undefined;
  /** Total events received so far (for the second meta line). */
  eventCount?: number | undefined;
  className?: string | undefined;
  /** Optional override for the activity line. */
  label?: string | undefined;
}

export function ResearchingBanner({
  startedAt,
  latestEvent,
  eventCount,
  className,
  label,
}: ResearchingBannerProps) {
  const activity = label ?? getEventActivity(latestEvent?.type);
  const stepIndex = latestEvent?.step_index;
  const showMeta =
    typeof stepIndex === "number" ||
    (typeof eventCount === "number" && eventCount > 0);

  const metaParts: string[] = [];
  if (typeof stepIndex === "number") {
    metaParts.push(`step ${stepIndex.toString()}`);
  }
  if (typeof eventCount === "number" && eventCount > 0) {
    metaParts.push(
      `${eventCount.toString()} ${eventCount === 1 ? "event" : "events"}`,
    );
  }

  return (
    <GlassSurface
      role="status"
      aria-live="polite"
      data-testid="researching-banner"
      variant="subtle"
      elevation="sm"
      radius="md"
      className={cn(
        "mx-auto mt-6 flex w-full max-w-3xl flex-col gap-1 px-4 py-3",
        "text-sm text-[var(--text-secondary)]",
        className,
      )}
    >
      <div className="flex items-center gap-3">
        <AnimatedDots label={activity} />
        <span className="flex-1" data-testid="researching-activity">
          {activity}
        </span>
        {startedAt !== undefined ? <ElapsedClock startedAt={startedAt} /> : null}
      </div>
      {showMeta ? (
        <span
          className="text-xs text-[var(--text-muted)]"
          data-testid="researching-meta"
        >
          {metaParts.join(" · ")}
        </span>
      ) : null}
    </GlassSurface>
  );
}
