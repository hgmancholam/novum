/**
 * ServiceHealthWarningModal — warns the user that some external services are
 * unavailable due to connectivity or credential issues (BRD-27).
 *
 * Pure presentational. Caller is responsible for filtering the services list
 * to only include non-ok, non-disabled entries before passing them here.
 */

import { X, AlertTriangle } from "lucide-react";

import { cn } from "@/lib/cn";
import type { ServiceHealth } from "@/types/health";

const STATUS_LABEL: Record<string, string> = {
  down: "Unreachable",
  no_key: "Missing credentials",
  degraded: "Degraded",
};

export interface ServiceHealthWarningModalProps {
  services: readonly ServiceHealth[];
  onClose: () => void;
  className?: string;
}

export function ServiceHealthWarningModal({
  services,
  onClose,
  className,
}: ServiceHealthWarningModalProps) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="svc-warning-title"
      className={cn(
        "fixed inset-0 z-50 flex items-center justify-center",
        className,
      )}
    >
      {/* Backdrop — click outside closes */}
      <div
        aria-hidden="true"
        data-testid="svc-warning-backdrop"
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="relative z-10 w-full max-w-md rounded-xl border border-(--glass-border) bg-(--bg-secondary) p-6 shadow-2xl">
        {/* Close button */}
        <button
          type="button"
          aria-label="Close warning"
          data-testid="svc-warning-close"
          onClick={onClose}
          className="absolute right-4 top-4 rounded p-1 text-(--text-tertiary) transition-colors hover:text-(--text-primary)"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>

        {/* Header */}
        <div className="mb-4 flex items-start gap-3">
          <AlertTriangle
            aria-hidden="true"
            className="mt-0.5 h-5 w-5 shrink-0 text-(--semantic-warning)"
          />
          <div>
            <h2
              id="svc-warning-title"
              className="text-sm font-semibold text-(--text-primary)"
            >
              Some external services are unavailable
            </h2>
            <p className="mt-1 text-xs text-(--text-secondary)">
              These are connectivity or credential issues with third-party
              providers — not bugs in Novum. Research will continue using the
              services that are reachable.
            </p>
          </div>
        </div>

        {/* Affected services list */}
        <ul aria-label="Affected services" className="mb-5 space-y-1.5">
          {services.map((svc) => (
            <li
              key={svc.id}
              className="flex items-center justify-between gap-2 text-xs"
            >
              <span className="font-medium text-(--text-primary)">
                {svc.name}
              </span>
              <span className="rounded px-1.5 py-0.5 bg-(--semantic-warning)/10 text-(--semantic-warning)">
                {STATUS_LABEL[svc.status] ?? svc.status}
              </span>
            </li>
          ))}
        </ul>

        {/* Dismiss */}
        <button
          type="button"
          data-testid="svc-warning-dismiss"
          onClick={onClose}
          className="w-full rounded-lg bg-(--bg-primary) px-4 py-2 text-xs font-medium text-(--text-primary) transition-colors hover:opacity-80"
        >
          Got it, continue
        </button>
      </div>
    </div>
  );
}
