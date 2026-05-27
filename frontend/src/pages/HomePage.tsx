/**
 * HomePage — Route: /
 * Owns: useUser, useRunHistory (via HistoryPanelContainer), useCreateRun (via NewRunContainer).
 * See ui-prototype.md §8.2 (Pages).
 */

import { AppShell, CenterPanel, TracePanel } from "@/components/templates";
import { TraceEmpty } from "@/components/molecules/TraceEmpty";
import { TraceHeader } from "@/components/organisms/TraceHeader";
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
      header={<TraceHeader eventCount={0} isStreaming={false} />}
      body={<TraceEmpty />}
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
