/**
 * ActionBar organism — header of the center panel (BRD-13 §4.9, RF-08, RF-11).
 *
 * V1 ships cancel + resume + fork (IP-15). The Fork button is enabled when
 * `forkableEventCount > 0` and an `onFork` handler is provided. When a run
 * has just been resumed, `showPostResumeNotice` renders the IP-15 microcopy
 * inline below the toolbar.
 *
 * Resume affordance appears only when the run stopped with `errored` or
 * `user_cancelled` (per RF-11, only those branches are resumable).
 *
 * Pure presentational. Callbacks injected by the page-level container.
 */

import { Button } from "@/components/atoms";
import { cn } from "@/lib/cn";
import { POST_RESUME_NOTICE } from "@/lib/microcopy";
import type { StopReason } from "@/types/events";
import type { RunStatus } from "@/types/run";

export interface ActionBarProps {
  status: RunStatus | undefined;
  stopReason?: StopReason | null | undefined;
  onCancel: () => void;
  isCancelling: boolean;
  onResume?: (() => void) | undefined;
  isResuming?: boolean | undefined;
  onFork?: (() => void) | undefined;
  isForking?: boolean | undefined;
  /** Number of forkable events available in the current run (IP-15). */
  forkableEventCount?: number | undefined;
  /** Render the post-resume notice (IP-15) — set after a successful resume
   *  until the agent emits new events. */
  showPostResumeNotice?: boolean | undefined;
  className?: string | undefined;
}

const RESUMABLE: ReadonlySet<StopReason> = new Set<StopReason>([
  "errored",
  "user_cancelled",
]);

const FORK_TOOLTIP_DISABLED =
  "No forkable points yet — wait for the agent to reach a plan or contradiction.";
const FORK_TOOLTIP_ENABLED = "Fork from a decision point";

export function ActionBar({
  status,
  stopReason = null,
  onCancel,
  isCancelling,
  onResume,
  isResuming = false,
  onFork,
  isForking = false,
  forkableEventCount = 0,
  showPostResumeNotice = false,
  className,
}: ActionBarProps) {
  const isRunning = status === "running";
  const cancelDisabled = !isRunning || isCancelling;
  const showResume =
    !isRunning && stopReason !== null && stopReason !== undefined
      ? RESUMABLE.has(stopReason)
      : false;
  const forkEnabled = forkableEventCount > 0 && onFork !== undefined;

  return (
    <div
      data-testid="action-bar"
      className={cn("flex flex-col gap-2", className)}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
          <span
            data-testid="live-dot"
            aria-hidden="true"
            className={cn(
              "inline-block h-2 w-2 rounded-full",
              isRunning ? "animate-pulse" : ""
            )}
            style={{
              backgroundColor: isRunning
                ? "var(--semantic-success)"
                : "var(--semantic-neutral)",
            }}
          />
          <span>{isRunning ? "Live" : "Stopped"}</span>
        </div>

        <div className="flex items-center gap-2">
          {showResume ? (
            <Button
              variant="secondary"
              size="sm"
              type="button"
              onClick={onResume}
              loading={isResuming}
              aria-label="Resume run"
              data-testid="resume-button"
            >
              Resume
            </Button>
          ) : null}
          <Button
            variant="ghost"
            size="sm"
            type="button"
            disabled={!forkEnabled}
            title={forkEnabled ? FORK_TOOLTIP_ENABLED : FORK_TOOLTIP_DISABLED}
            aria-label="Fork run"
            data-testid="fork-button"
            onClick={onFork}
            loading={isForking}
          >
            Fork
            {forkEnabled ? (
              <span
                data-testid="fork-count"
                className="ml-1 rounded-full bg-[var(--bg-tertiary)] px-1.5 text-[10px] leading-tight text-[var(--text-secondary)]"
              >
                {forkableEventCount}
              </span>
            ) : null}
          </Button>
          <Button
            variant="danger"
            size="sm"
            type="button"
            onClick={onCancel}
            disabled={cancelDisabled}
            loading={isCancelling}
            aria-label="Cancel run"
            data-testid="cancel-button"
          >
            Cancel
          </Button>
        </div>
      </div>
      {showPostResumeNotice ? (
        <p
          role="status"
          data-testid="post-resume-notice"
          className="rounded-[var(--radius-sm)] border border-[var(--glass-border)] bg-[var(--bg-tertiary)] px-3 py-2 text-xs text-[var(--text-secondary)]"
        >
          {POST_RESUME_NOTICE}
        </p>
      ) : null}
    </div>
  );
}
