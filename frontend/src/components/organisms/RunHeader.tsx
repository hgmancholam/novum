/**
 * RunHeader organism — header for a run (status badge + meta + elapsed clock).
 * Rendered above the body of `CenterPanel`. Pure presentational.
 */

import {
  ElapsedClock,
  LineageBadge,
  MetaRow,
  StatusBadge,
} from "@/components/molecules";
import { cn } from "@/lib/cn";
import type { AnswerKind } from "@/types/events";
import type { Run, RunStatus } from "@/types/run";

export interface RunHeaderProps {
  run: Run;
  status: RunStatus;
  /** RF-17: forwarded to StatusBadge so a best-effort budget stop is labeled
   * "Best-effort answer" instead of the generic "Stopped on budget". */
  answerKind?: AnswerKind | null | undefined;
  className?: string | undefined;
}

export function RunHeader({ run, status, answerKind, className }: RunHeaderProps) {
  const badgeStatus =
    status === "running"
      ? ("running" as const)
      : run.stopReason === "judge_confirmed"
        ? ("completed" as const)
        : ("stopped" as const);

  return (
    <div
      data-testid="run-header"
      className={cn(
        "mx-auto flex w-full max-w-3xl flex-col gap-2 pt-2",
        className
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <StatusBadge
          status={badgeStatus}
          {...(run.stopReason !== null
            ? { stopReason: run.stopReason }
            : {})}
          {...(answerKind !== null && answerKind !== undefined
            ? { answerKind }
            : {})}
        />
        {status === "running" ? <ElapsedClock startedAt={run.startedAt} /> : null}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <MetaRow
          startedAt={run.startedAt}
          stoppedAt={run.stoppedAt}
          outputFormat={run.outputFormat}
          confidenceThreshold={run.confidenceThreshold}
          ownerUsername={run.ownerUsername}
          llmProvider={run.llmProvider}
        />
        <LineageBadge parentRunId={run.parentRunId} />
      </div>
    </div>
  );
}
