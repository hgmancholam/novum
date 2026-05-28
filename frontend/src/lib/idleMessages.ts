/**
 * Rotating Spanish reassurance messages shown when the agent has been
 * working without emitting new events for a while. Keeps the user
 * engaged on long-running queries.
 */

import { useEffect, useState } from "react";

export const IDLE_REASSURANCE_MESSAGES: readonly string[] = [
  "Sigo investigando…",
  "Esto está tomando un poco más de lo esperado…",
  "Cruzando información de varias fuentes…",
  "Pensando con calma para no equivocarme…",
  "Buscando fuentes confiables…",
  "Verificando lo que encontré…",
  "Casi listo, dame un momento más…",
  "Comparando perspectivas para responderte mejor…",
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
