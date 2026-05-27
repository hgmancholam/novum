/**
 * RunPage — Route: /runs/:runId
 * Owns: HistoryPanelContainer + CenterPanelContainer + TracePanelContainer.
 * See ui-prototype.md §8.2 (Pages).
 */

import { AppShell } from "@/components/templates";
import { HistoryPanelContainer } from "./HistoryPanelContainer";
import { CenterPanelContainer } from "./CenterPanelContainer";
import { TracePanelContainer } from "./TracePanelContainer";

export default function RunPage() {
  return (
    <AppShell
      left={<HistoryPanelContainer />}
      center={<CenterPanelContainer />}
      right={<TracePanelContainer />}
    />
  );
}
