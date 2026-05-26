/**
 * CenterPanelView organism — composes Question + (Researching | StopReason).
 * See BRD-13 §4.2 and IP-13 §2.
 *
 * Pure presentational. The page-level `CenterPanelContainer` provides data
 * via `useRun` and renders this view inside the `templates/CenterPanel` body.
 */

import { QuestionDisplay } from "./QuestionDisplay";
import { ResearchingBanner } from "./ResearchingBanner";
import { StopReasonCard } from "./StopReasonCard";
import { cn } from "@/lib/cn";
import type { Run, RunStatus } from "@/types/run";

export interface CenterPanelViewProps {
  run: Run;
  status: RunStatus;
  className?: string | undefined;
}

export function CenterPanelView({ run, status, className }: CenterPanelViewProps) {
  return (
    <div
      data-testid="center-panel-view"
      className={cn("flex w-full flex-col gap-2 pt-2", className)}
    >
      <QuestionDisplay question={run.question} />

      {status === "running" ? (
        <ResearchingBanner />
      ) : run.stopReason !== null ? (
        <StopReasonCard reason={run.stopReason} />
      ) : null}
    </div>
  );
}
