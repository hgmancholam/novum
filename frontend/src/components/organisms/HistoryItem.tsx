/**
 * HistoryItem organism — one entry in the history list (BRD-20 §4.5–4.6).
 *
 * Wraps the existing {@link RunRow} button with a `motion.li` so we can
 * animate row removal via the parent `AnimatePresence`, and renders the
 * delete affordance (trash icon, bottom-right). The affordance is:
 *
 * - Hidden while `run.status === "running"` (cannot delete in-flight
 *   work — backend returns 409).
 * - Revealed on group hover / keyboard focus (`group-hover` /
 *   `focus-visible`), per ui-prototype.md §3.2 L2/L4 and §1.4
 *   (transition ≤ 120 ms; respects `motion-reduce`).
 * - Labeled exactly "Delete run" per BRD-20 §14.3.
 *
 * Stop propagation on click so the trash never triggers row selection.
 */

import { memo, type MouseEvent } from "react";
import { motion } from "motion/react";
import { Trash2 } from "lucide-react";

import { cn } from "@/lib/cn";
import type { RunSummary } from "@/types/history";

import { RunRow } from "./RunRow";

export interface HistoryItemProps {
  run: RunSummary;
  isSelected: boolean;
  onSelect: (runId: string) => void;
  onDelete?: ((runId: string) => void) | undefined;
}

const EXIT_TRANSITION = { duration: 0.18 };

export const HistoryItem = memo(function HistoryItem({
  run,
  isSelected,
  onSelect,
  onDelete,
}: HistoryItemProps) {
  const canDelete = onDelete !== undefined && run.status !== "running";

  const handleDelete = (event: MouseEvent<HTMLButtonElement>): void => {
    event.stopPropagation();
    onDelete?.(run.id);
  };

  return (
    <motion.li
      layout
      exit={{ opacity: 0, height: 0, marginTop: 0, marginBottom: 0 }}
      transition={EXIT_TRANSITION}
      className="group relative overflow-hidden"
      data-testid="history-item"
    >
      <RunRow run={run} isSelected={isSelected} onSelect={onSelect} />
      {canDelete ? (
        <button
          type="button"
          aria-label="Delete run"
          title="Delete run"
          data-testid="history-item-delete"
          onClick={handleDelete}
          className={cn(
            "absolute bottom-2 right-2 z-10 inline-flex h-7 w-7 items-center justify-center rounded",
            "text-(--text-muted) hover:text-(--semantic-danger)",
            "opacity-0 transition-opacity duration-120 ease-out",
            "group-hover:opacity-100 focus-visible:opacity-100",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]",
            "motion-reduce:transition-none"
          )}
        >
          <Trash2 aria-hidden="true" size={16} />
        </button>
      ) : null}
    </motion.li>
  );
});
