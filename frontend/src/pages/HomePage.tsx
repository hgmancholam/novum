/**
 * HomePage — Route: /
 * Owns: useUser, useRunHistory (via HistoryPanelContainer), useCreateRun (via NewRunContainer).
 * See ui-prototype.md §8.2 (Pages).
 */

import { AppShell, CenterPanel, TracePanel } from "@/components/templates";
import { TraceEmpty } from "@/components/molecules/TraceEmpty";
import { TraceHeader } from "@/components/organisms/TraceHeader";
import { useSelectionStore } from "@/stores/selectionStore";
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
  const isCollapsed = useSelectionStore((s) => s.isTracePanelCollapsed);
  const toggleCollapse = useSelectionStore((s) => s.toggleTracePanelCollapsed);
  return (
    <TracePanel
      isCollapsed={isCollapsed}
      header={
        <TraceHeader
          eventCount={0}
          isStreaming={false}
          isCollapsed={isCollapsed}
          onToggleCollapse={toggleCollapse}
        />
      }
      body={isCollapsed ? null : <TraceEmpty />}
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
