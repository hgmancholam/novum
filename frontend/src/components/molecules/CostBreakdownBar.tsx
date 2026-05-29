/**
 * CostBreakdownBar molecule — stacked bar + legend per provider (BRD-29 §4.6).
 *
 * Aggregates rows by `provider` (sum of `cost_usd`), assigns a stable color
 * via `providerColor()`, and renders both the visual bar and an accessible
 * legend list.
 */

import { useMemo } from "react";

import { CostBarSegment } from "@/components/atoms";
import { cn } from "@/lib/cn";
import { formatPct, formatUsd } from "@/lib/formatCost";
import type { ProviderCostRow } from "@/types/costs";

export interface CostBreakdownBarProps {
  rows: readonly ProviderCostRow[];
  className?: string;
}

interface ProviderAggregate {
  provider: string;
  cost: number;
  color: string;
}

const PROVIDER_COLOR_TOKENS: readonly string[] = [
  "var(--accent)",
  "color-mix(in srgb, var(--accent) 60%, transparent)",
  "var(--semantic-warning)",
  "var(--semantic-success)",
  "var(--text-muted)",
];

function providerColor(provider: string, index: number): string {
  const named: Record<string, string> = {
    anthropic: "var(--accent)",
    openai: "color-mix(in srgb, var(--accent) 60%, transparent)",
    google: "var(--semantic-warning)",
    github: "color-mix(in srgb, var(--accent) 80%, transparent)",
    tavily: "var(--semantic-success)",
    wikipedia: "var(--text-muted)",
  };
  return (
    named[provider.toLowerCase()] ??
    PROVIDER_COLOR_TOKENS[index % PROVIDER_COLOR_TOKENS.length] ??
    "var(--text-muted)"
  );
}

export function CostBreakdownBar({ rows, className }: CostBreakdownBarProps) {
  const { aggregates, total } = useMemo(() => {
    const map = new Map<string, number>();
    for (const r of rows) {
      map.set(r.provider, (map.get(r.provider) ?? 0) + r.cost_usd);
    }
    const sorted = [...map.entries()].sort((a, b) => b[1] - a[1]);
    const aggs: ProviderAggregate[] = sorted.map(([provider, cost], i) => ({
      provider,
      cost,
      color: providerColor(provider, i),
    }));
    const sum = aggs.reduce((s, a) => s + a.cost, 0);
    return { aggregates: aggs, total: sum };
  }, [rows]);

  if (rows.length === 0 || total <= 0) {
    return (
      <div
        data-testid="cost-breakdown-bar-empty"
        className={cn(
          "rounded-md border border-[var(--glass-border)] px-3 py-4 text-center text-xs text-[var(--text-muted)]",
          className
        )}
      >
        No cost recorded yet.
      </div>
    );
  }

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div
        data-testid="cost-breakdown-bar"
        className="flex h-2 w-full overflow-hidden rounded-full bg-[var(--glass-bg)]"
      >
        {aggregates.map((a) => (
          <CostBarSegment
            key={a.provider}
            provider={a.provider}
            value={a.cost}
            total={total}
            color={a.color}
          />
        ))}
      </div>
      <ul role="list" className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
        {aggregates.map((a) => {
          const pct = (a.cost / total) * 100;
          return (
            <li
              key={a.provider}
              className="inline-flex items-center gap-1.5 text-[var(--text-secondary)]"
            >
              <span
                aria-hidden="true"
                className="inline-block h-2 w-2 rounded-full"
                style={{ backgroundColor: a.color }}
              />
              <span className="capitalize">{a.provider}</span>
              <span className="font-mono text-[var(--text-muted)]">
                {formatUsd(a.cost)} · {formatPct(pct)}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
