/**
 * AnalyticsFilters molecule — date range + provider + kind selectors.
 *
 * Stateless: parent owns the filters object. Native HTML inputs keep
 * the bundle small and a11y straightforward.
 */

import { useCallback, useId } from "react";
import { RefreshCw, X } from "lucide-react";

import { Button } from "@/components/atoms";
import { cn } from "@/lib/cn";
import type { CostAnalyticsFilters } from "@/types/costAnalytics";

export interface AnalyticsFiltersProps {
  filters: CostAnalyticsFilters;
  onChange: (next: CostAnalyticsFilters) => void;
  onReset?: () => void;
  onRefresh?: () => void;
  isRefreshing?: boolean;
  providers?: string[];
  kinds?: string[];
  className?: string;
}

const DEFAULT_PROVIDERS = ["anthropic", "openai", "google", "github", "tavily", "wikipedia"];
const DEFAULT_KINDS = ["llm", "search", "fetch"];

export function AnalyticsFilters({
  filters,
  onChange,
  onReset,
  onRefresh,
  isRefreshing = false,
  providers,
  kinds,
  className,
}: AnalyticsFiltersProps) {
  const fromId = useId();
  const toId = useId();
  const providerOptions = providers ?? DEFAULT_PROVIDERS;
  const kindOptions = kinds ?? DEFAULT_KINDS;

  const setField = useCallback(
    <K extends keyof CostAnalyticsFilters>(
      key: K,
      value: CostAnalyticsFilters[K] | undefined
    ): void => {
      const next = { ...filters };
      if (value === undefined || value === "" || (Array.isArray(value) && value.length === 0)) {
        delete next[key];
      } else {
        next[key] = value;
      }
      onChange(next);
    },
    [filters, onChange]
  );

  const toggleArrayValue = useCallback(
    (key: "providers" | "kinds", value: string): void => {
      const current = filters[key] ?? [];
      const next = current.includes(value)
        ? current.filter((v) => v !== value)
        : [...current, value];
      setField(key, next.length > 0 ? next : undefined);
    },
    [filters, setField]
  );

  const hasActive =
    Boolean(filters.dateFrom) ||
    Boolean(filters.dateTo) ||
    (filters.providers?.length ?? 0) > 0 ||
    (filters.kinds?.length ?? 0) > 0;

  return (
    <div
      data-testid="analytics-filters"
      className={cn(
        "flex flex-wrap items-end gap-4 rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--glass-bg)] p-4",
        className
      )}
    >
      <div className="flex flex-col gap-1">
        <label htmlFor={fromId} className="text-xs text-(--text-secondary)">
          From
        </label>
        <input
          id={fromId}
          type="date"
          value={filters.dateFrom ?? ""}
          onChange={(e) => { setField("dateFrom", e.target.value || undefined); }}
          className="rounded-md border border-[var(--glass-border)] bg-transparent px-2 py-1 text-sm text-(--text-primary)"
        />
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor={toId} className="text-xs text-(--text-secondary)">
          To
        </label>
        <input
          id={toId}
          type="date"
          value={filters.dateTo ?? ""}
          onChange={(e) => { setField("dateTo", e.target.value || undefined); }}
          className="rounded-md border border-[var(--glass-border)] bg-transparent px-2 py-1 text-sm text-(--text-primary)"
        />
      </div>

      <fieldset className="flex flex-col gap-1">
        <legend className="text-xs text-(--text-secondary)">Provider</legend>
        <div className="flex flex-wrap gap-1" role="group" aria-label="Providers">
          {providerOptions.map((p) => {
            const active = filters.providers?.includes(p) ?? false;
            return (
              <button
                key={p}
                type="button"
                onClick={() => { toggleArrayValue("providers", p); }}
                aria-pressed={active}
                className={cn(
                  "rounded-full border px-2 py-0.5 text-xs capitalize transition-colors",
                  active
                    ? "border-(--accent) bg-(--accent-soft) text-(--text-primary)"
                    : "border-[var(--glass-border)] text-(--text-secondary) hover:text-(--text-primary)"
                )}
              >
                {p}
              </button>
            );
          })}
        </div>
      </fieldset>

      <fieldset className="flex flex-col gap-1">
        <legend className="text-xs text-(--text-secondary)">Kind</legend>
        <div className="flex flex-wrap gap-1" role="group" aria-label="Kinds">
          {kindOptions.map((k) => {
            const active = filters.kinds?.includes(k) ?? false;
            return (
              <button
                key={k}
                type="button"
                onClick={() => { toggleArrayValue("kinds", k); }}
                aria-pressed={active}
                className={cn(
                  "rounded-full border px-2 py-0.5 text-xs uppercase transition-colors",
                  active
                    ? "border-(--accent) bg-(--accent-soft) text-(--text-primary)"
                    : "border-[var(--glass-border)] text-(--text-secondary) hover:text-(--text-primary)"
                )}
              >
                {k}
              </button>
            );
          })}
        </div>
      </fieldset>

      <div className="ml-auto flex items-end gap-2">
        {hasActive && onReset !== undefined ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={onReset}
            aria-label="Reset filters"
          >
            <X className="h-3 w-3" /> Reset
          </Button>
        ) : null}
        {onRefresh !== undefined ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={onRefresh}
            disabled={isRefreshing}
            aria-label="Refresh analytics"
          >
            <RefreshCw
              className={cn("h-3 w-3", isRefreshing && "animate-spin")}
            />
            Refresh
          </Button>
        ) : null}
      </div>
    </div>
  );
}
