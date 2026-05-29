/**
 * ServiceHealthWarningModal — friendly floating tip card that appears when
 * some services are unavailable (BRD-27).
 *
 * Styled as a glass bubble (no dark overlay), bottom-right corner.
 * Pure presentational. Caller filters services to non-ok/non-disabled.
 */

import { X, Info } from "lucide-react";
import { motion } from "motion/react";

import { cn } from "@/lib/cn";
import type { ServiceHealth } from "@/types/health";

const STATUS_LABEL: Record<string, string> = {
  down: "unreachable",
  no_key: "not configured",
  degraded: "degraded",
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
    <>
      {/* Invisible click-outside catcher — sits between footer (z-40) and card */}
      <div
        aria-hidden="true"
        data-testid="svc-warning-backdrop"
        className="fixed inset-0 z-[45]"
        onClick={onClose}
      />

      {/* Floating glass card */}
      <motion.div
        role="status"
        aria-label="Service notice"
        data-testid="svc-warning-panel"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ type: "spring", stiffness: 380, damping: 30 }}
        className={cn(
          "fixed bottom-10 right-4 z-50 w-72",
          "rounded-2xl border border-(--glass-border)/60",
          "bg-(--bg-secondary)/80 backdrop-blur-xl",
          "shadow-xl shadow-black/20",
          "p-4",
          className,
        )}
      >
        {/* Header row */}
        <div className="mb-2 flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5">
            <Info
              aria-hidden="true"
              className="h-3.5 w-3.5 text-(--text-tertiary)"
            />
            <span className="text-xs font-medium text-(--text-primary)">
              Quick heads-up
            </span>
          </div>
          <button
            type="button"
            aria-label="Dismiss notice"
            data-testid="svc-warning-close"
            onClick={onClose}
            className="rounded p-0.5 text-(--text-tertiary) transition-colors hover:text-(--text-primary)"
          >
            <X className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        </div>

        {/* Body */}
        <p className="mb-3 text-xs leading-relaxed text-(--text-secondary)">
          Some of our services are having a moment. Novum will keep going with
          what’s available — results might be a bit limited.
        </p>

        {/* Affected services */}
        <ul aria-label="Affected services" className="mb-3 space-y-1">
          {services.map((svc) => (
            <li
              key={svc.id}
              className="flex items-center justify-between gap-2 text-[11px]"
            >
              <span className="text-(--text-secondary)">{svc.name}</span>
              <span className="text-(--text-tertiary)">
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
          className="w-full rounded-xl py-1.5 text-[11px] font-medium text-(--text-tertiary) transition-colors hover:bg-(--glass-border)/30 hover:text-(--text-primary)"
        >
          Got it
        </button>
      </motion.div>
    </>
  );
}
