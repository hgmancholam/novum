/**
 * DiffPage — Route: /diff/:runA/:runB
 * Owns: useUser, useRun(a), useRun(b), useRunHistory
 * See ui-prototype.md §8.2 (Pages).
 *
 * Renders:
 * - AppShell with center renders DiffView (C12), trace renders TimelineDiff (T5)
 */

import { useParams } from "react-router-dom";

export default function DiffPage() {
  const { runA, runB } = useParams<{ runA: string; runB: string }>();

  // TODO: Implement with useRun hooks for both runs
  // This is a placeholder for BRD-15 (Fork & Resume)
  return (
    <div className="flex h-screen items-center justify-center bg-[var(--bg-primary)]">
      <div className="text-center">
        <h1 className="text-xl font-semibold text-[var(--text-primary)]">
          Comparing Runs
        </h1>
        <p className="mt-2 text-[var(--text-secondary)]">
          {runA} vs {runB}
        </p>
      </div>
    </div>
  );
}
