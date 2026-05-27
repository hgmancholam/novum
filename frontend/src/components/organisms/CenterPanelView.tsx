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

import { OutcomeBar } from "@/components/atoms";
import { cn } from "@/lib/cn";
import type { Run, RunStatus } from "@/types/run";

import { QuestionDisplay } from "./QuestionDisplay";
import { ResearchingBanner } from "./ResearchingBanner";
import { RunHeader } from "./RunHeader";
import { StopReasonCard } from "./StopReasonCard";
import { TrustSummary } from "./TrustSummary";

export interface CenterPanelViewProps {
  run: Run;
  status: RunStatus;
  className?: string | undefined;
}

export function CenterPanelView({ run, status, className }: CenterPanelViewProps) {
  const isTerminal = status === "stopped" && run.stopReason !== null;

  return (
    <div
      data-testid="center-panel-view"
      className={cn("flex w-full flex-col gap-4", className)}
    >
      {isTerminal && run.stopReason !== null ? (
        <OutcomeBar reason={run.stopReason} />
      ) : null}

      <RunHeader run={run} status={status} />
      <QuestionDisplay question={run.question} />

      {status === "running" ? (
        <ResearchingBanner startedAt={run.startedAt} />
      ) : isTerminal && run.stopReason !== null ? (
        <div className="flex flex-col gap-3">
          <TrustSummary run={run} />
          <StopReasonCard reason={run.stopReason} />
        </div>
      ) : null}
    </div>
  );
}
