/**
 * HistoryFilters organism — filter controls for the history list.
 * BRD-12 §4.8 and ui-prototype.md §3.2 (state L7).
 *
 * Stateless: parent owns `filters`.
 */

import { useCallback, useId } from "react";

import { Button } from "@/components/atoms";
import { cn } from "@/lib/cn";
import type { StopReason } from "@/types/events";
import type { HistoryFilterValues, RunStatus } from "@/types/history";

export interface HistoryFiltersProps {
  filters: HistoryFilterValues;
  onChange: (next: HistoryFilterValues) => void;
  className?: string;
}

const statusOptions: ReadonlyArray<{ value: RunStatus; label: string }> = [
  { value: "running", label: "Running" },
  { value: "completed", label: "Completed" },
  { value: "stopped", label: "Stopped" },
];

const stopReasonOptions: ReadonlyArray<{ value: StopReason; label: string }> = [
  { value: "judge_confirmed", label: "Confirmed" },
  { value: "honest_unanswerable", label: "Unanswerable" },
  { value: "honest_contradiction", label: "Contradiction" },
  { value: "honest_ambiguous", label: "Ambiguous" },
  { value: "stopped_by_budget", label: "Budget" },
  { value: "user_cancelled", label: "Cancelled" },
  { value: "errored", label: "Errored" },
];

export function hasActiveFilters(filters: HistoryFilterValues): boolean {
  return Boolean(
    filters.status ??
      filters.stopReason ??
      (filters.search !== undefined && filters.search.trim() !== "")
  );
}

function withoutStatus(filters: HistoryFilterValues): HistoryFilterValues {
  const { status: _status, ...rest } = filters;
  return rest;
}

function withoutStopReason(
  filters: HistoryFilterValues
): HistoryFilterValues {
  const { stopReason: _reason, ...rest } = filters;
  return rest;
}

function withoutSearch(filters: HistoryFilterValues): HistoryFilterValues {
  const { search: _search, ...rest } = filters;
  return rest;
}

export function HistoryFilters({
  filters,
  onChange,
  className,
}: HistoryFiltersProps) {
  const searchId = useId();

  const handleSearch = useCallback(
    (value: string): void => {
      if (value === "") {
        onChange(withoutSearch(filters));
      } else {
        onChange({ ...filters, search: value });
      }
    },
    [filters, onChange]
  );

  const handleStatusToggle = useCallback(
    (status: RunStatus): void => {
      if (filters.status === status) {
        onChange(withoutStatus(filters));
      } else {
        onChange({ ...filters, status });
      }
    },
    [filters, onChange]
  );

  const handleStopReasonToggle = useCallback(
    (reason: StopReason): void => {
      if (filters.stopReason === reason) {
        onChange(withoutStopReason(filters));
      } else {
        onChange({ ...filters, stopReason: reason });
      }
    },
    [filters, onChange]
  );

  const handleClear = useCallback((): void => {
    onChange({});
  }, [onChange]);

  const active = hasActiveFilters(filters);

  return (
    <div
      data-testid="history-filters"
      className={cn(
        "flex flex-col gap-2 border-b border-[var(--glass-border)] px-3 py-3",
        className
      )}
    >
      <label htmlFor={searchId} className="sr-only">
        Search history
      </label>
      <input
        id={searchId}
        type="search"
        value={filters.search ?? ""}
        onChange={(e) => {
          handleSearch(e.target.value);
        }}
        placeholder="Search questions…"
        className={cn(
          "w-full rounded-md border border-[var(--glass-border)]",
          "bg-[var(--bg-tertiary)] px-3 py-2 text-sm",
          "text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]",
          "focus:border-[var(--accent)] focus:outline-none"
        )}
      />

      <div
        role="group"
        aria-label="Filter by status"
        className="flex flex-wrap gap-1"
      >
        {statusOptions.map(({ value, label }) => {
          const pressed = filters.status === value;
          return (
            <button
              key={value}
              type="button"
              aria-pressed={pressed}
              onClick={() => {
                handleStatusToggle(value);
              }}
              className={cn(
                "rounded-full px-2.5 py-1 text-xs transition-colors duration-150",
                pressed
                  ? "bg-[var(--accent)] text-[var(--text-primary)]"
                  : "bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:bg-[var(--glass-bg)]"
              )}
            >
              {label}
            </button>
          );
        })}
      </div>

      <details className="text-xs text-[var(--text-secondary)]">
        <summary className="cursor-pointer select-none py-1">
          Stop reason
        </summary>
        <div
          role="group"
          aria-label="Filter by stop reason"
          className="mt-1 flex flex-wrap gap-1"
        >
          {stopReasonOptions.map(({ value, label }) => {
            const pressed = filters.stopReason === value;
            return (
              <button
                key={value}
                type="button"
                aria-pressed={pressed}
                onClick={() => {
                  handleStopReasonToggle(value);
                }}
                className={cn(
                  "rounded-full px-2.5 py-1 text-xs transition-colors duration-150",
                  pressed
                    ? "bg-[var(--accent)] text-[var(--text-primary)]"
                    : "bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:bg-[var(--glass-bg)]"
                )}
              >
                {label}
              </button>
            );
          })}
        </div>
      </details>

      {active ? (
        <Button
          variant="ghost"
          size="sm"
          onClick={handleClear}
          className="self-end"
        >
          Clear filters
        </Button>
      ) : null}
    </div>
  );
}
