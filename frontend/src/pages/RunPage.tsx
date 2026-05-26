/**
 * RunPage — Route: /runs/:runId
 * Owns: HistoryPanelContainer + CenterPanelContainer + TracePanel (BRD-15 stub).
 * See ui-prototype.md §8.2 (Pages).
 */

import { AppShell, TracePanel } from "@/components/templates";
import { HistoryPanelContainer } from "./HistoryPanelContainer";
import { CenterPanelContainer } from "./CenterPanelContainer";

export default function RunPage() {
  return (
    <AppShell
      left={<HistoryPanelContainer />}
      center={<CenterPanelContainer />}
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
