/**
 * TracePanelContainer — page-level data owner for the right panel.
 *
 * Subscribes to `useRunStream` (only when a `runId` is available) and
 * renders the `templates/TracePanel` geometry with the live header + body.
 *
 * On HomePage there is no `runId`; HomePage mounts `<TraceEmpty/>` directly
 * inside `TracePanel` and does NOT use this container. Per
 * `eslint.config.js`, only `pages/` may call `useRun*` hooks.
 */

import { useParams } from "react-router-dom";

import { TraceEmpty } from "@/components/molecules/TraceEmpty";
import { TraceHeader } from "@/components/organisms/TraceHeader";
import { TraceTimeline } from "@/components/organisms/TraceTimeline";
import { TracePanel } from "@/components/templates";
import { useRunStream } from "@/hooks/useRunStream";

export function TracePanelContainer() {
  const { runId } = useParams<{ runId: string }>();
  const { events, isConnected, isComplete } = useRunStream({
    runId,
    enabled: runId !== undefined && runId.length > 0,
  });

  const isStreaming = isConnected && !isComplete;

  return (
    <TracePanel
      header={
        <TraceHeader eventCount={events.length} isStreaming={isStreaming} />
      }
      body={
        runId === undefined || runId.length === 0 ? (
          <TraceEmpty />
        ) : (
          <TraceTimeline events={events} isComplete={isComplete} />
        )
      }
    />
  );
}
