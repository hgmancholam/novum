/**
 * HistoryFilters organism — filter controls for the history list.
 * BRD-12 §4.8 and ui-prototype.md §3.2 (state L7).
 *
 * Stateless: parent owns `filters`.
 */

import { useCallback, useId } from "react";
import {
  Activity,
  CheckCircle2,
  CircleStop,
  RefreshCw,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Button } from "@/components/atoms";
import { cn } from "@/lib/cn";
import type { StopReason } from "@/types/events";
import type { HistoryFilterValues, RunStatus } from "@/types/history";

export interface HistoryFiltersProps {
  filters: HistoryFilterValues;
  onChange: (next: HistoryFilterValues) => void;
  onRefresh?: () => void;
  isRefreshing?: boolean;
  className?: string;
}

interface StatusOption {
  value: RunStatus;
  label: string;
  Icon: LucideIcon;
}

const statusOptions: ReadonlyArray<StatusOption> = [
  { value: "running", label: "Running", Icon: Activity },
  { value: "completed", label: "Completed", Icon: CheckCircle2 },
  { value: "stopped", label: "Stopped", Icon: CircleStop },
];

const stopReasonOptions: ReadonlyArray<{ value: StopReason; label: string }> = [
  { value: "judge_confirmed", label: "Confirmed" },
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
  onRefresh,
  isRefreshing = false,
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
      // Switching away from (or off of) "stopped" must also drop the
      // stopReason — otherwise the user keeps a hidden, contradictory
      // filter active (e.g. status=running AND stopReason=errored).
      if (filters.status === status) {
        onChange(withoutStopReason(withoutStatus(filters)));
      } else {
        onChange({ ...withoutStopReason(filters), status });
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
  const showStopReason = filters.status === "stopped";

  const iconButtonBase = cn(
    "inline-flex h-8 w-8 items-center justify-center rounded-md",
    "transition-colors duration-150",
    "focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
  );

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

      <div className="flex items-center justify-between">
        <div
          role="group"
          aria-label="Filter by status"
          className="flex items-center gap-1"
        >
          {statusOptions.map(({ value, label, Icon }) => {
            const pressed = filters.status === value;
            return (
              <button
                key={value}
                type="button"
                aria-pressed={pressed}
                aria-label={label}
                title={label}
                onClick={() => {
                  handleStatusToggle(value);
                }}
                className={cn(
                  iconButtonBase,
                  pressed
                    ? "bg-[var(--accent)] text-[var(--text-primary)]"
                    : "text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]"
                )}
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
              </button>
            );
          })}
        </div>

        {onRefresh ? (
          <button
            type="button"
            onClick={onRefresh}
            disabled={isRefreshing}
            aria-label="Refresh history"
            title="Refresh"
            data-testid="history-refresh"
            className={cn(
              iconButtonBase,
              "text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]",
              "disabled:cursor-not-allowed disabled:opacity-60"
            )}
          >
            <RefreshCw
              className={cn("h-4 w-4", isRefreshing && "animate-spin")}
              aria-hidden="true"
            />
          </button>
        ) : null}
      </div>

      {showStopReason ? (
        <div
          role="group"
          aria-label="Filter by stop reason"
          data-testid="history-stop-reason-group"
          className="flex flex-wrap gap-1"
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
      ) : null}

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
