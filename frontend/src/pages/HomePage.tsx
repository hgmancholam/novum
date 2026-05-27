/**
 * HomePage — Route: /
 * Owns: useUser, useRunHistory (via HistoryPanelContainer), useCreateRun (via NewRunContainer).
 * See ui-prototype.md §8.2 (Pages).
 */

import { AppShell, CenterPanel, TracePanel } from "@/components/templates";
import { HistoryPanelContainer } from "./HistoryPanelContainer";
import { NewRunContainer } from "./NewRunContainer";

function CenterStart() {
  return (
    <CenterPanel
      body={<NewRunContainer />}
    />
  );
}

function TracePlaceholder() {
  return (
    <TracePanel
      header={
        <h2 className="text-sm font-medium text-[var(--text-primary)]">
          Trace
        </h2>
      }
      body={
        <p className="text-xs text-[var(--text-secondary)]">
          The event log will appear here once research starts.
        </p>
      }
    />
  );
}

export default function HomePage() {
  return (
    <AppShell
      left={<HistoryPanelContainer />}
      center={<CenterStart />}
      right={<TracePlaceholder />}
    />
  );
}
