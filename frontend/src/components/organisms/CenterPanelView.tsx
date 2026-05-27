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
import { FormatSelector } from "@/components/molecules";
import { cn } from "@/lib/cn";
import type { Run, RunStatus } from "@/types/run";
import type { StructuredAnswerData } from "@/types/events";

import { QuestionDisplay } from "./QuestionDisplay";
import {
  ResearchingBanner,
  type ResearchingBannerLatestEvent,
} from "./ResearchingBanner";
import { RunHeader } from "./RunHeader";
import { SourcesCard, type SourceEntry } from "./SourcesCard";
import { StopReasonCard } from "./StopReasonCard";
import { StructuredAnswer } from "./StructuredAnswer";
import { StructuredBlocks } from "./StructuredBlocks";
import { TrustSummary, type JudgeConfidenceMetrics } from "./TrustSummary";

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
  /** Final answer — prose-rendered (BRD-16). */
  answerProse?: string | null | undefined;
  /** Final answer — structured-rendered (BRD-16 enhancement). */
  answerStructured?: string | null | undefined;
  /** Final answer — typed structured JSON (RF-10). Frontend renders blocks natively. */
  answerStructuredData?: StructuredAnswerData | null | undefined;
  /** Currently active view format for client-side switching. */
  viewFormat?: string | undefined;
  /** Called when the user clicks a different format button. */
  onViewFormatChange?: ((format: string) => void) | undefined;
  /** Evidence sources collected during the run (from EvidenceAdded events). */
  sources?: readonly SourceEntry[] | undefined;
  /** Confidence metrics from the JudgeRuled event (RF-12). */
  judgeConfidence?: JudgeConfidenceMetrics | null | undefined;
  className?: string | undefined;
}

export function CenterPanelView({
  run,
  status,
  suppressResearchingBanner = false,
  latestEvent,
  eventCount,
  answerProse,
  answerStructured,
  answerStructuredData,
  viewFormat,
  onViewFormatChange,
  sources,
  judgeConfidence,
  className,
}: CenterPanelViewProps) {
  const isTerminal = status === "stopped" && run.stopReason !== null;
  const hasAnswer =
    isTerminal &&
    run.stopReason === "judge_confirmed" &&
    (answerProse !== null && answerProse !== undefined);

  const isStructured = viewFormat === "structured";

  // Determine which markdown content to show as fallback (when no JSON data).
  const activeContent: string | null = isStructured
    ? (answerStructured ?? answerProse ?? null)
    : (answerProse ?? null);

  // Show JSON-block view when in structured mode AND backend provided typed data.
  const showStructuredBlocks =
    hasAnswer &&
    isStructured &&
    answerStructuredData !== null &&
    answerStructuredData !== undefined;

  // Show format switcher when any structured rendering is available.
  const showFormatSelector =
    hasAnswer &&
    ((answerStructured !== null && answerStructured !== undefined) ||
      (answerStructuredData !== null && answerStructuredData !== undefined)) &&
    onViewFormatChange !== undefined;

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
            {hasAnswer && activeContent !== null ? (
              <>
                {showFormatSelector ? (
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-(--text-muted)">
                      Format
                    </span>
                    <FormatSelector
                      value={viewFormat ?? "prose"}
                      onChange={onViewFormatChange!}
                    />
                  </div>
                ) : null}
                {showStructuredBlocks ? (
                  <StructuredBlocks
                    data={answerStructuredData!}
                    data-testid="run-answer"
                  />
                ) : (
                  <StructuredAnswer
                    content={activeContent}
                    outputFormat={
                      (viewFormat ?? run.outputFormat ?? "prose") as
                        | "prose"
                        | "structured"
                    }
                    data-testid="run-answer"
                  />
                )}
                {sources !== undefined && sources.length > 0 ? (
                  <SourcesCard sources={sources} />
                ) : null}
              </>
            ) : null}
            <TrustSummary
              run={run}
              judgeConfidence={judgeConfidence}
              sourceCount={sources?.length}
            />
            <StopReasonCard reason={run.stopReason} />
          </div>
        ) : null}
      </div>
    </GlassSurface>
  );
}
