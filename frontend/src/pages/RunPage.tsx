/**
 * RunPage — Route: /runs/:runId and /runs/:runId?fork=:eventId
 * Owns: useUser, useRun(runId), useEventStream(runId), useRunHistory
 * See ui-prototype.md §8.2 (Pages).
 *
 * Renders:
 * - AppShell with center varying per run state (C3–C11), trace shows T2/T3
 */

import { useParams, useSearchParams } from "react-router-dom";

export default function RunPage() {
  const { runId } = useParams<{ runId: string }>();
  const [searchParams] = useSearchParams();
  const forkEventId = searchParams.get("fork");

  // TODO: Implement with useRun, useEventStream hooks
  // This is a placeholder for BRD-13 (Center Panel)
  return (
    <div className="flex h-screen items-center justify-center bg-[var(--bg-primary)]">
      <div className="text-center">
        <h1 className="text-xl font-semibold text-[var(--text-primary)]">
          Run: {runId}
        </h1>
        {forkEventId && (
          <p className="mt-2 text-[var(--text-secondary)]">
            Forking from event: {forkEventId}
          </p>
        )}
      </div>
    </div>
  );
}
