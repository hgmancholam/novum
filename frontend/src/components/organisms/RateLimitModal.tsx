/**
 * RateLimitModal organism.
 *
 * Shown when an `AgentErrored` event carries
 * `error_code === "llm_pool_rate_limited"`, signalling that every GitHub
 * Models PAT in the rotation pool returned 429 within a single fallback
 * sweep. Purely presentational: visibility and dismissal are owned by
 * the page-level container.
 */

import { useEffect, useRef } from "react";

import { Button, GlassSurface } from "@/components/atoms";
import { cn } from "@/lib/cn";
import {
  RATE_LIMIT_MODAL_CLOSE,
  RATE_LIMIT_MODAL_DESCRIPTION,
  RATE_LIMIT_MODAL_HINT,
  RATE_LIMIT_MODAL_TITLE,
} from "@/lib/microcopy";

export interface RateLimitModalProps {
  isOpen: boolean;
  onClose: () => void;
  className?: string | undefined;
}

export function RateLimitModal({
  isOpen,
  onClose,
  className,
}: RateLimitModalProps) {
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
      aria-labelledby="rate-limit-modal-title"
      aria-describedby="rate-limit-modal-description"
      data-testid="rate-limit-modal"
      className={cn(
        "fixed inset-0 z-50 flex items-center justify-center bg-[var(--overlay-scrim)]",
        className
      )}
      onClick={onClose}
    >
      <GlassSurface
        data-testid="rate-limit-modal-surface"
        variant="strong"
        elevation="lg"
        radius="lg"
        onClick={(e) => {
          e.stopPropagation();
        }}
        className="w-full max-w-md p-6"
      >
        <h2
          id="rate-limit-modal-title"
          className="mb-2 text-lg font-semibold text-[var(--text-primary)]"
        >
          {RATE_LIMIT_MODAL_TITLE}
        </h2>
        <p
          id="rate-limit-modal-description"
          className="mb-3 text-sm text-[var(--text-secondary)]"
        >
          {RATE_LIMIT_MODAL_DESCRIPTION}
        </p>
        <p className="mb-5 rounded-[var(--radius-sm)] border border-dashed border-[var(--glass-border)] bg-[var(--bg-tertiary)] p-3 text-xs text-[var(--text-muted)]">
          {RATE_LIMIT_MODAL_HINT}
        </p>

        <div className="flex justify-end">
          <Button
            ref={closeButtonRef}
            type="button"
            variant="primary"
            size="md"
            onClick={onClose}
            data-testid="rate-limit-modal-close"
          >
            {RATE_LIMIT_MODAL_CLOSE}
          </Button>
        </div>
      </GlassSurface>
    </div>
  );
}
