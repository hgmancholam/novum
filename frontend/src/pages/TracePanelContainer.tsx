/**
 * TracePanelContainer — page-level data owner for the right panel.
 *
 * Subscribes to `useRunStream` (only when a `runId` is available) and
 * renders the `templates/TracePanel` geometry with the live header + body.
 *
 * On HomePage there is no `runId`; HomePage mounts `<TraceEmpty/>` directly
 * inside `TracePanel` and does NOT use this container. Per
 * `eslint.config.js`, only `pages/` may call `useRun*` hooks.
 *
 * IP-24 Phase 5: Supports trace panel collapse via selectionStore.
 */

import { useParams } from "react-router-dom";

import { TraceEmpty } from "@/components/molecules/TraceEmpty";
import { TraceHeader } from "@/components/organisms/TraceHeader";
import { TraceTimeline } from "@/components/organisms/TraceTimeline";
import { TracePanel } from "@/components/templates";
import { useRunStream } from "@/hooks/useRunStream";
import { useSelectionStore } from "@/stores/selectionStore";

export function TracePanelContainer() {
  const { runId } = useParams<{ runId: string }>();
  const { events, isConnected, isComplete } = useRunStream({
    runId,
    enabled: runId !== undefined && runId.length > 0,
  });

  const isStreaming = isConnected && !isComplete;

  // IP-24 Phase 5: Collapse state
  const isCollapsed = useSelectionStore((s) => s.isTracePanelCollapsed);
  const toggleCollapse = useSelectionStore((s) => s.toggleTracePanelCollapsed);

  return (
    <TracePanel
      header={
        <TraceHeader
          eventCount={events.length}
          isStreaming={isStreaming}
          isCollapsed={isCollapsed}
          onToggleCollapse={toggleCollapse}
        />
      }
      body={
        runId === undefined || runId.length === 0 ? (
          <TraceEmpty />
        ) : isCollapsed ? null : (
          <TraceTimeline events={events} isComplete={isComplete} />
        )
      }
    />
  );
}
