/**
 * CenterPanelView organism — composes the full run view (BRD-13 §4.2).
 *
 * Layout:
 *   1. `OutcomeBar`  — 4 px colored strip on terminal states (C6-C10)
 *   2. `RunHeader`   — status badge + meta chips + elapsed clock
 *   3. `QuestionDisplay`
 *   4. running?       → `RunFeed` (live feed, IP-24)
 *      terminal?      → `RunFeed` (collapsed) + `TrustSummary` + `StopReasonCard`
 *
 * Pure presentational. The page-level `CenterPanelContainer` provides data
 * via `useRun` and renders this view inside the `templates/CenterPanel` body.
 */

import { OutcomeBar, GlassSurface } from "@/components/atoms";
import { AnswerToolbar, type AnswerViewMode } from "@/components/molecules";
import { cn } from "@/lib/cn";
import { useCallback, useState } from "react";
import type { Run, RunStatus } from "@/types/run";
import type { AnswerKind, StructuredAnswerData, RunStreamEvent } from "@/types/events";
import {
  isAnimateAnswerEnabled,
  hasAnswerBeenAnimated,
  markAnswerAnimated,
} from "@/lib/answerAnimation";

import { QuestionDisplay } from "./QuestionDisplay";
import { RunHeader } from "./RunHeader";
import { SourcesCard, type SourceEntry } from "./SourcesCard";
import { StopReasonCard } from "./StopReasonCard";
import { StructuredAnswer } from "./StructuredAnswer";
import { StructuredBlocks } from "./StructuredBlocks";
import { TrustSummary, type JudgeConfidenceMetrics, type StructuralConfidenceFallback } from "./TrustSummary";
import { RunFeed } from "./RunFeed";

export interface CenterPanelViewProps {
  run: Run;
  status: RunStatus;
  /** Stream events for RunFeed (IP-24). */
  events?: readonly RunStreamEvent[] | undefined;
  /** Final answer — prose-rendered (BRD-16). */
  answerProse?: string | null | undefined;
  /** Final answer — structured-rendered (BRD-16 enhancement). */
  answerStructured?: string | null | undefined;
  /** Final answer — typed structured JSON (RF-10). Frontend renders blocks natively. */
  answerStructuredData?: StructuredAnswerData | null | undefined;
  /** RF-17: shape of the answer (best_effort surfaces a warning badge). */
  answerKind?: AnswerKind | null | undefined;
  /** Currently active view format for client-side switching. */
  viewFormat?: string | undefined;
  /** Called when the user clicks a different format button. */
  onViewFormatChange?: ((format: string) => void) | undefined;
  /** Evidence sources collected during the run (from EvidenceAdded events). */
  sources?: readonly SourceEntry[] | undefined;
  /** Confidence metrics from the JudgeRuled event (RF-12). */
  judgeConfidence?: JudgeConfidenceMetrics | null | undefined;
  /** Structural fallback surfaced when the judge never confirmed (PR-1 Mejora 2.2). */
  structuralFallback?: StructuralConfidenceFallback | null | undefined;
  /** IP-15 §9: hide feed when in post-resume limbo (until new agent work). */
  showPostResumeNotice?: boolean | undefined;
  /** Resume CTA forwarded to StopReasonCard for errored / user_cancelled runs. */
  onResume?: (() => void) | undefined;
  isResuming?: boolean | undefined;
  className?: string | undefined;
}

export function CenterPanelView({
  run,
  status,
  events,
  answerProse,
  answerStructured,
  answerStructuredData,
  answerKind,
  viewFormat,
  onViewFormatChange,
  sources,
  judgeConfidence,
  structuralFallback,
  showPostResumeNotice = false,
  onResume,
  isResuming = false,
  className,
}: CenterPanelViewProps) {
  const isTerminal = status === "stopped" && run.stopReason !== null;
  const hasProse = answerProse !== null && answerProse !== undefined;
  // C3 fallback: when the judge cap fires, the orchestrator still drafts a
  // best-effort answer and stops with STOPPED_BY_BUDGET. We render it like a
  // normal answer but tagged with a warning badge so the user sees the
  // difference vs a judge-confirmed run.
  const isBestEffortFallback =
    isTerminal &&
    run.stopReason === "stopped_by_budget" &&
    answerKind === "best_effort" &&
    hasProse;
  const hasAnswer =
    (isTerminal && run.stopReason === "judge_confirmed" && hasProse) ||
    isBestEffortFallback;

  // IP-24 Phase 3.5: Stable `shouldAnimate` for the lifetime of the
  // component instance. Computed once on mount so re-renders triggered
  // by the typewriter itself do not flip it back to `false`.
  const [shouldAnimate] = useState<boolean>(() =>
    isAnimateAnswerEnabled() && hasAnswer && !hasAnswerBeenAnimated(run.id),
  );

  // Mark as animated only after the typewriter finishes its run.
  const handleAnswerAnimationComplete = useCallback(() => {
    markAnswerAnimated(run.id);
  }, [run.id]);

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

  // Show format toggle when a structured rendering is available alongside
  // the prose answer. Without an alternative rendering the toggle would be a
  // no-op, so we hide it.
  const hasStructuredRendering =
    (answerStructured !== null && answerStructured !== undefined) ||
    (answerStructuredData !== null && answerStructuredData !== undefined);
  const showFormatToggle =
    hasAnswer && hasStructuredRendering && onViewFormatChange !== undefined;

  const handleViewModeChange = useCallback(
    (mode: AnswerViewMode) => {
      onViewFormatChange?.(mode);
    },
    [onViewFormatChange],
  );

  const currentViewMode: AnswerViewMode = isStructured ? "structured" : "prose";
  const markdownSource =
    answerStructured ?? answerProse ?? activeContent ?? "";

  return (
    <div
      data-testid="center-panel-view"
      className={cn("mx-auto flex w-full max-w-3xl flex-col gap-5", className)}
    >
      {/* Card 1 — Question + run header */}
      <GlassSurface
        variant="default"
        elevation="lg"
        radius="xl"
        className="relative overflow-hidden"
      >
        {isTerminal && run.stopReason !== null ? (
          <OutcomeBar reason={run.stopReason} />
        ) : null}
        <div className="flex flex-col gap-6 px-6 py-6">
          <RunHeader run={run} status={status} answerKind={answerKind} />
          <QuestionDisplay question={run.question} />
        </div>
      </GlassSurface>

      {/* Card 2 — Live reasoning feed */}
      {events !== undefined &&
      events.length > 0 &&
      !showPostResumeNotice ? (
        <GlassSurface
          variant="default"
          elevation="md"
          radius="xl"
          data-testid="run-feed-card"
        >
          <div className="px-6 py-5">
            <RunFeed events={events} isComplete={isTerminal} />
          </div>
        </GlassSurface>
      ) : null}

      {/* Card 3 — Verified answer + trust + stop reason */}
      {isTerminal && run.stopReason !== null ? (
        <GlassSurface
          variant="default"
          elevation="lg"
          radius="xl"
          data-testid="run-answer-card"
        >
          <div className="flex flex-col gap-3 px-6 py-6">
            {hasAnswer && activeContent !== null ? (
              <>
                <div className="flex justify-end">
                  <AnswerToolbar
                    markdownSource={markdownSource}
                    plainText={answerProse ?? markdownSource}
                    viewMode={currentViewMode}
                    onViewModeChange={
                      onViewFormatChange !== undefined
                        ? handleViewModeChange
                        : undefined
                    }
                    showToggle={showFormatToggle}
                  />
                </div>
                {showStructuredBlocks ? (
                  <StructuredBlocks
                    data={answerStructuredData!}
                    animate={shouldAnimate}
                    onAnimationComplete={handleAnswerAnimationComplete}
                    data-testid="run-answer"
                  />
                ) : (
                  <StructuredAnswer
                    content={activeContent}
                    animate={shouldAnimate}
                    onAnimationComplete={handleAnswerAnimationComplete}
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
              structuralFallback={structuralFallback}
              sourceCount={sources?.length}
            />
            <StopReasonCard
              reason={run.stopReason}
              onResume={onResume}
              isResuming={isResuming}
            />
          </div>
        </GlassSurface>
      ) : null}
    </div>
  );
}
