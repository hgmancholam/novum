/**
 * DiffPage — Route: /diff/:runA/:runB
 * Owns: useUser, useRun(a), useRun(b), useRunHistory (wired in future BRDs).
 * See ui-prototype.md §8.2 (Pages).
 */

import { useParams } from "react-router-dom";
import {
  AppShell,
  HistoryPanel,
  CenterPanel,
  TracePanel,
} from "@/components/templates";

export default function DiffPage() {
  const { runA, runB } = useParams<{ runA: string; runB: string }>();

  return (
    <AppShell
      left={
        <HistoryPanel
          header={
            <h2 className="text-sm font-medium text-[var(--text-primary)]">
              History
            </h2>
          }
          body={
            <p className="px-2 text-sm text-[var(--text-secondary)]">
              Run history will appear here.
            </p>
          }
        />
      }
      center={
        <CenterPanel
          body={
            <div className="mx-auto max-w-2xl pt-16 text-center">
              <h1 className="text-xl font-semibold text-[var(--text-primary)]">
                Comparing runs
              </h1>
              <p className="mt-2 text-sm text-[var(--text-secondary)]">
                {runA ?? "?"} vs {runB ?? "?"}
              </p>
            </div>
          }
        />
      }
      right={
        <TracePanel
          header={
            <h2 className="text-sm font-medium text-[var(--text-primary)]">
              Timeline diff
            </h2>
          }
          body={
            <p className="text-xs text-[var(--text-secondary)]">
              Diff timeline appears here.
            </p>
          }
        />
      }
    />
  );
}
