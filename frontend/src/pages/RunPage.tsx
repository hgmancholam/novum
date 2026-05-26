/**
 * RunPage — Route: /runs/:runId and /runs/:runId?fork=:eventId
 * Owns: useUser, useRun(runId), useEventStream(runId), useRunHistory (wired in future BRDs).
 * See ui-prototype.md §8.2 (Pages).
 */

import { useParams, useSearchParams } from "react-router-dom";
import { AppShell, CenterPanel, TracePanel } from "@/components/templates";
import { HistoryPanelContainer } from "./HistoryPanelContainer";

export default function RunPage() {
  const { runId } = useParams<{ runId: string }>();
  const [searchParams] = useSearchParams();
  const forkEventId = searchParams.get("fork");

  return (
    <AppShell
      left={<HistoryPanelContainer />}
      center={
        <CenterPanel
          body={
            <div className="mx-auto max-w-2xl pt-16 text-center">
              <h1 className="text-xl font-semibold text-[var(--text-primary)]">
                Run {runId ?? "unknown"}
              </h1>
              {forkEventId !== null ? (
                <p className="mt-2 text-sm text-[var(--text-secondary)]">
                  Forking from event {forkEventId}.
                </p>
              ) : null}
            </div>
          }
        />
      }
      right={
        <TracePanel
          header={
            <h2 className="text-sm font-medium text-[var(--text-primary)]">
              Trace
            </h2>
          }
          body={
            <p className="text-xs text-[var(--text-secondary)]">
              The event log will appear here.
            </p>
          }
        />
      }
    />
  );
}
