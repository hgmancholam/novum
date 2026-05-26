/**
 * ActionBar organism — header of the center panel (BRD-13 §4.9, RF-08).
 *
 * V1 ships cancel-only. The Fork button is rendered but disabled with a
 * tooltip pointing to BRD-15 (Trace Panel will own the picker).
 *
 * Pure presentational. Callbacks injected by the page-level container.
 */

import { Button } from "@/components/atoms";
import { cn } from "@/lib/cn";
import type { RunStatus } from "@/types/run";

export interface ActionBarProps {
  status: RunStatus | undefined;
  onCancel: () => void;
  isCancelling: boolean;
  onFork?: (() => void) | undefined;
  isForking?: boolean | undefined;
  className?: string | undefined;
}

const FORK_TOOLTIP = "Select a step from the trace (coming soon)";

export function ActionBar({
  status,
  onCancel,
  isCancelling,
  onFork,
  isForking = false,
  className,
}: ActionBarProps) {
  const isRunning = status === "running";
  const cancelDisabled = !isRunning || isCancelling;

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
