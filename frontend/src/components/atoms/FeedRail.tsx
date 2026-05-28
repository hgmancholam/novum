/**
 * FeedRail atom — vertical line forming the spine of the live feed.
 * Tone switches between neutral (inactive) and active (run in progress).
 * IP-24 Phase 1.
 */

import { cn } from "@/lib/cn";

export interface FeedRailProps {
  tone?: "neutral" | "active";
  className?: string | undefined;
}

export function FeedRail({ tone = "neutral", className }: FeedRailProps) {
  const color =
    tone === "active"
      ? "bg-[var(--feed-rail-active)]"
      : "bg-[var(--feed-rail)]";

  return (
    <div
      data-tone={tone}
      className={cn(
        "absolute left-4 top-0 bottom-0 w-px",
        color,
        className
      )}
      aria-hidden="true"
    />
  );
}
