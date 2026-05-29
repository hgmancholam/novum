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
import { cn } from "@/lib/cn";
import { TraceCostPanelContainer } from "./TraceCostPanelContainer";

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

  // BRD-29 / IP-29 — active right-panel tab
  const traceTab = useSelectionStore((s) => s.traceTab);
  const setTraceTab = useSelectionStore((s) => s.setTraceTab);

  const hasRun = runId !== undefined && runId.length > 0;

  return (
    <TracePanel
      isCollapsed={isCollapsed}
      header={
        <TraceHeader
          eventCount={events.length}
          isStreaming={isStreaming}
          isCollapsed={isCollapsed}
          onToggleCollapse={toggleCollapse}
        />
      }
      body={
        !hasRun ? (
          <TraceEmpty />
        ) : isCollapsed ? null : (
          <div className="flex flex-col gap-3">
            <div
              role="tablist"
              aria-label="Trace panel tabs"
              className="flex items-center gap-1 border-b border-[var(--glass-border)]"
            >
              {(
                [
                  { id: "trace" as const, label: "Trace" },
                  { id: "cost" as const, label: "Cost" },
                ]
              ).map((tab) => {
                const active = traceTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    role="tab"
                    aria-selected={active}
                    data-testid={`trace-tab-${tab.id}`}
                    onClick={() => {
                      setTraceTab(tab.id);
                    }}
                    className={cn(
                      "px-3 py-1.5 text-xs font-medium transition-colors",
                      "border-b-2 -mb-px",
                      active
                        ? "border-[var(--accent)] text-[var(--accent)]"
                        : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                    )}
                  >
                    {tab.label}
                  </button>
                );
              })}
            </div>
            {traceTab === "cost" ? (
              <TraceCostPanelContainer runId={runId} />
            ) : (
              <TraceTimeline events={events} isComplete={isComplete} />
            )}
          </div>
        )
      }
    />
  );
}
