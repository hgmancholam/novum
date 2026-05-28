/**
 * Rotating reassurance messages shown when the agent has been working
 * without emitting new events for a while. Keeps the user engaged on
 * long-running queries.
 */

import { useEffect, useState } from "react";

export const IDLE_REASSURANCE_MESSAGES: readonly string[] = [
  "Still researching…",
  "This is taking a bit longer than expected…",
  "Cross-checking information across sources…",
  "Thinking it through carefully…",
  "Looking for reliable sources…",
  "Verifying what I found…",
  "Almost there, just a moment more…",
  "Comparing perspectives to give you a better answer…",
];

/**
 * Returns a rotating reassurance message when the last event is older
 * than `idleAfterMs`. Returns `null` while activity is fresh or the run
 * is not active.
 *
 * The message rotates every `rotateMs` milliseconds.
 */
export function useIdleReassurance(
  isActive: boolean,
  lastEventTimestampMs: number | null,
  idleAfterMs: number = 12_000,
  rotateMs: number = 10_000,
): string | null {
  const [now, setNow] = useState(() => Date.now());
  const [index, setIndex] = useState(
    () => Math.floor(Math.random() * IDLE_REASSURANCE_MESSAGES.length),
  );

  useEffect(() => {
    if (!isActive) return;
    const tick = window.setInterval(() => {
      setNow(Date.now());
    }, 1000);
    return () => { window.clearInterval(tick); };
  }, [isActive]);

  useEffect(() => {
    if (!isActive) return;
    const rotate = window.setInterval(() => {
      setIndex((i) => (i + 1) % IDLE_REASSURANCE_MESSAGES.length);
    }, rotateMs);
    return () => { window.clearInterval(rotate); };
  }, [isActive, rotateMs]);

  if (!isActive) return null;
  if (lastEventTimestampMs === null) return null;
  if (now - lastEventTimestampMs < idleAfterMs) return null;

  return IDLE_REASSURANCE_MESSAGES[index] ?? null;
}
