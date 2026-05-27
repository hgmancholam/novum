/**
 * ForkModal organism — IP-15 (Fork & Resume).
 *
 * Lists the forkable events of a stopped run and lets the user pick one to
 * branch from. Pure presentational: the page-level container owns the
 * `fork()` mutation, loading and error state.
 *
 * Atoms + molecules + tokens only — does not call data hooks
 * (atomic-design rule, `eslint.config.js`).
 */

import { useEffect, useRef } from "react";

import { Button, ForkableEventRow, GlassSurface } from "@/components/atoms";
import { cn } from "@/lib/cn";
import {
  FORK_MODAL_DESCRIPTION,
  FORK_MODAL_EMPTY_STATE,
  FORK_MODAL_TITLE,
} from "@/lib/microcopy";

export interface ForkModalEvent {
  id: string;
  type: string;
  stepIndex: number;
  summary?: string | undefined;
}

export interface ForkModalProps {
  isOpen: boolean;
  events: readonly ForkModalEvent[];
  onSelect: (eventId: string) => void;
  onClose: () => void;
  isForking?: boolean | undefined;
  pendingEventId?: string | null | undefined;
  error?: Error | null | undefined;
  className?: string | undefined;
}

export function ForkModal({
  isOpen,
  events,
  onSelect,
  onClose,
  isForking = false,
  pendingEventId = null,
  error = null,
  className,
}: ForkModalProps) {
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    closeButtonRef.current?.focus();
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
    };
  }, [isOpen, onClose]);

  if (!isOpen) {
    return null;
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="fork-modal-title"
      aria-describedby="fork-modal-description"
      data-testid="fork-modal"
      className={cn(
        "fixed inset-0 z-50 flex items-center justify-center bg-[var(--overlay-scrim)]",
        className
      )}
      onClick={onClose}
    >
      <GlassSurface
        data-testid="fork-modal-surface"
        variant="strong"
        elevation="lg"
        radius="lg"
        onClick={(e) => {
          e.stopPropagation();
        }}
        className="w-full max-w-lg p-6"
      >
        <h2
          id="fork-modal-title"
          className="mb-2 text-lg font-semibold text-[var(--text-primary)]"
        >
          {FORK_MODAL_TITLE}
        </h2>
        <p
          id="fork-modal-description"
          className="mb-4 text-sm text-[var(--text-secondary)]"
        >
          {FORK_MODAL_DESCRIPTION}
        </p>

        {events.length === 0 ? (
          <p
            data-testid="fork-modal-empty"
            className="rounded-[var(--radius-sm)] border border-dashed border-[var(--glass-border)] bg-[var(--bg-tertiary)] p-3 text-center text-xs text-[var(--text-muted)]"
          >
            {FORK_MODAL_EMPTY_STATE}
          </p>
        ) : (
          <ul
            data-testid="fork-modal-list"
            className="flex max-h-80 flex-col gap-2 overflow-y-auto"
          >
            {events.map((evt) => (
              <ForkableEventRow
                key={evt.id}
                eventId={evt.id}
                type={evt.type}
                stepIndex={evt.stepIndex}
                summary={evt.summary}
                isPending={isForking && pendingEventId === evt.id}
                onSelect={onSelect}
              />
            ))}
          </ul>
        )}

        {error !== null && error !== undefined ? (
          <p
            role="alert"
            data-testid="fork-modal-error"
            className="mt-3 text-sm text-[var(--semantic-danger)]"
          >
            Could not fork: {error.message}
          </p>
        ) : null}

        <div className="mt-5 flex justify-end">
          <Button
            ref={closeButtonRef}
            type="button"
            variant="ghost"
            size="md"
            onClick={onClose}
            data-testid="fork-modal-close"
          >
            Close
          </Button>
        </div>
      </GlassSurface>
    </div>
  );
}
