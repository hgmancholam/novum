/**
 * ActionBar organism — header of the center panel (BRD-13 §4.9, RF-08, RF-11).
 *
 * V1 ships cancel + resume. The Fork button is rendered but disabled with a
 * tooltip pointing to BRD-15 (Trace Panel will own the picker).
 *
 * Resume affordance appears only when the run stopped with `errored` or
 * `user_cancelled` (per RF-11, only those branches are resumable).
 *
 * Pure presentational. Callbacks injected by the page-level container.
 */

import { Button } from "@/components/atoms";
import { cn } from "@/lib/cn";
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
  className?: string | undefined;
}

const FORK_TOOLTIP = "Select a step from the trace (coming soon)";
const RESUMABLE: ReadonlySet<StopReason> = new Set<StopReason>([
  "errored",
  "user_cancelled",
]);

export function ActionBar({
  status,
  stopReason = null,
  onCancel,
  isCancelling,
  onResume,
  isResuming = false,
  onFork,
  isForking = false,
  className,
}: ActionBarProps) {
  const isRunning = status === "running";
  const cancelDisabled = !isRunning || isCancelling;
  const showResume =
    !isRunning && stopReason !== null && stopReason !== undefined
      ? RESUMABLE.has(stopReason)
      : false;

  return (
    <div
      data-testid="action-bar"
      className={cn("flex items-center justify-between gap-3", className)}
    >
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
          disabled
          title={FORK_TOOLTIP}
          aria-label="Fork run"
          data-testid="fork-button"
          onClick={onFork}
          loading={isForking}
        >
          Fork
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
  );
}
