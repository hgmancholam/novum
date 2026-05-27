/**
 * ElapsedClock molecule — ticking elapsed time since `startedAt`.
 * Used by `ResearchingBanner` (C4) and `RunHeader` while a run is running.
 *
 * Formats:
 *   < 60 s  → "Xs"
 *   < 60 m  → "Xm Ys"
 *   else    → "Xh Ym"
 */

import { useEffect, useState } from "react";

import { cn } from "@/lib/cn";

export interface ElapsedClockProps {
  /** ISO timestamp when the run started. */
  startedAt: string;
  /** Stop ticking once true (used on terminal states). */
  frozen?: boolean | undefined;
  /** Override the "now" reference — useful for tests. */
  now?: Date | undefined;
  className?: string | undefined;
}

export function formatElapsed(elapsedMs: number): string {
  const totalSec = Math.max(0, Math.floor(elapsedMs / 1000));
  if (totalSec < 60) {
    return `${totalSec}s`;
  }
  const minutes = Math.floor(totalSec / 60);
  if (minutes < 60) {
    const seconds = totalSec % 60;
    return `${minutes}m ${seconds}s`;
  }
  const hours = Math.floor(minutes / 60);
  const remMin = minutes % 60;
  return `${hours}h ${remMin}m`;
}

export function ElapsedClock({
  startedAt,
  frozen = false,
  now,
  className,
}: ElapsedClockProps) {
  const [tick, setTick] = useState<number>(() =>
    (now ?? new Date()).getTime()
  );

  useEffect(() => {
    if (frozen) {
      return;
    }
    const id = setInterval(() => {
      setTick(Date.now());
    }, 1000);
    return () => {
      clearInterval(id);
    };
  }, [frozen]);

  const startMs = new Date(startedAt).getTime();
  const reference = now !== undefined ? now.getTime() : tick;
  const text = formatElapsed(reference - startMs);

  return (
    <span
      data-testid="elapsed-clock"
      aria-label={`Elapsed ${text}`}
      className={cn(
        "tabular-nums text-xs text-[var(--text-secondary)]",
        className
      )}
    >
      {text}
    </span>
  );
}
