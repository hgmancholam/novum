/**
 * CenterPanelView organism — composes the full run view (BRD-13 §4.2).
 *
 * Layout:
 *   1. `OutcomeBar`  — 4 px colored strip on terminal states (C6-C10)
 *   2. `RunHeader`   — status badge + meta chips + elapsed clock
 *   3. `QuestionDisplay`
 *   4. running?       → `ResearchingBanner` (with elapsed clock)
 *      terminal?      → `TrustSummary` + `StopReasonCard`
 *
 * Pure presentational. The page-level `CenterPanelContainer` provides data
 * via `useRun` and renders this view inside the `templates/CenterPanel` body.
 */

import { OutcomeBar, GlassSurface } from "@/components/atoms";
import { cn } from "@/lib/cn";
import type { Run, RunStatus } from "@/types/run";

import { QuestionDisplay } from "./QuestionDisplay";
import {
  ResearchingBanner,
  type ResearchingBannerLatestEvent,
} from "./ResearchingBanner";
import { RunHeader } from "./RunHeader";
import { StopReasonCard } from "./StopReasonCard";
import { TrustSummary } from "./TrustSummary";

export interface CenterPanelViewProps {
  run: Run;
  status: RunStatus;
  /** When true, do not render the `ResearchingBanner` even if the run is
   *  running (IP-15 F6: post-resume agent restart is deferred). */
  suppressResearchingBanner?: boolean | undefined;
  /** Most recent event emitted by the agent — drives the banner activity copy. */
  latestEvent?: ResearchingBannerLatestEvent | undefined;
  /** Total events received so far — drives the banner meta line. */
  eventCount?: number | undefined;
  className?: string | undefined;
}

export function CenterPanelView({
  run,
  status,
  suppressResearchingBanner = false,
  latestEvent,
  eventCount,
  className,
}: CenterPanelViewProps) {
  const isTerminal = status === "stopped" && run.stopReason !== null;

  return (
    <GlassSurface
      data-testid="center-panel-view"
      variant="default"
      elevation="lg"
      radius="xl"
      className={cn(
        "mx-auto flex w-full max-w-3xl flex-col gap-4 overflow-hidden",
        className
      )}
    >
      {isTerminal && run.stopReason !== null ? (
        <OutcomeBar reason={run.stopReason} />
      ) : null}

      <div className="flex flex-col gap-4 px-6 py-6">
        <RunHeader run={run} status={status} />
        <QuestionDisplay question={run.question} />

        {status === "running" && !suppressResearchingBanner ? (
          <ResearchingBanner
            startedAt={run.startedAt}
            latestEvent={latestEvent}
            eventCount={eventCount}
          />
        ) : isTerminal && run.stopReason !== null ? (
          <div className="flex flex-col gap-3">
            <TrustSummary run={run} />
            <StopReasonCard reason={run.stopReason} />
          </div>
        ) : null}
      </div>
    </GlassSurface>
  );
}
