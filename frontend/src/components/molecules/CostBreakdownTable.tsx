/**
 * CostBreakdownTable molecule — sortable per-row cost table (BRD-29 §4.6, AC-04).
 *
 * Free-tier rows (cost_usd === 0) render USD as "—" (AC-09 graceful display).
 * Headers are buttons that toggle the active sort.
 */

import { ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/cn";
import { formatPct, formatTokens, formatUsd } from "@/lib/formatCost";
import type { ProviderCostRow } from "@/types/costs";

export type CostSortKey = "cost" | "calls" | "tokens";
export type SortDir = "asc" | "desc";

export interface CostBreakdownTableProps {
  rows: readonly ProviderCostRow[];
  sortBy?: CostSortKey;
  className?: string;
}

function sortRows(
  rows: readonly ProviderCostRow[],
  key: CostSortKey,
  dir: SortDir
): ProviderCostRow[] {
  const mult = dir === "asc" ? 1 : -1;
  const copy = [...rows];
  copy.sort((a, b) => {
    let av: number;
    let bv: number;
    switch (key) {
      case "calls":
        av = a.calls;
        bv = b.calls;
        break;
      case "tokens":
        av = a.prompt_tokens + a.completion_tokens;
        bv = b.prompt_tokens + b.completion_tokens;
        break;
      case "cost":
      default:
        av = a.cost_usd;
        bv = b.cost_usd;
        break;
    }
    return (av - bv) * mult;
  });
  return copy;
}

export function CostBreakdownTable({
  rows,
  sortBy = "cost",
  className,
}: CostBreakdownTableProps) {
  const [activeKey, setActiveKey] = useState<CostSortKey>(sortBy);
  const [dir, setDir] = useState<SortDir>("desc");

  const sorted = sortRows(rows, activeKey, dir);

  const toggle = (key: CostSortKey): void => {
    if (key === activeKey) {
      setDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setActiveKey(key);
      setDir("desc");
    }
  };

  const renderHeader = (
    key: CostSortKey | null,
    label: string,
    align: "left" | "right" = "left"
  ): React.ReactNode => {
    const alignClass = align === "right" ? "text-right" : "text-left";
    if (key === null) {
      return (
        <th
          scope="col"
          className={cn(
            "px-2 py-1.5 text-xs font-medium text-[var(--text-secondary)]",
            alignClass
          )}
        >
          {label}
        </th>
      );
    }
    const isActive = activeKey === key;
    const Icon = isActive && dir === "asc" ? ChevronUp : ChevronDown;
    return (
      <th
        scope="col"
        className={cn(
          "px-2 py-1.5 text-xs font-medium text-[var(--text-secondary)]",
          alignClass
        )}
      >
        <button
          type="button"
          onClick={() => {
            toggle(key);
          }}
          className={cn(
            "inline-flex items-center gap-0.5 hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:underline",
            align === "right" && "flex-row-reverse"
          )}
        >
          <span>{label}</span>
          <Icon
            className={cn(
              "h-3 w-3",
              isActive
                ? "text-[var(--accent)]"
                : "text-[var(--text-muted)]"
            )}
            aria-hidden="true"
          />
        </button>
      </th>
    );
  };

  return (
    <div className={cn("max-h-72 overflow-y-auto", className)}>
      <table
        data-testid="cost-breakdown-table"
        className="w-full border-collapse text-xs"
      >
        <thead className="sticky top-0 bg-[var(--bg-elevated,var(--glass-bg))]">
          <tr className="border-b border-[var(--glass-border)]">
            {renderHeader(null, "Provider")}
            {renderHeader(null, "Kind")}
            {renderHeader(null, "Model")}
            {renderHeader("calls", "Calls", "right")}
            {renderHeader("tokens", "Prompt", "right")}
            {renderHeader("tokens", "Completion", "right")}
            {renderHeader(null, "Units", "right")}
            {renderHeader("cost", "USD", "right")}
            {renderHeader(null, "%", "right")}
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 ? (
            <tr>
              <td
                colSpan={9}
                className="px-2 py-4 text-center text-[var(--text-muted)]"
              >
                No cost rows.
              </td>
            </tr>
          ) : (
            sorted.map((r) => {
              const usd =
                r.cost_usd > 0 ? formatUsd(r.cost_usd) : "—";
              const pct = r.cost_usd > 0 ? formatPct(r.pct_of_total) : "—";
              return (
                <tr
                  key={`${r.provider}|${r.kind}|${r.model ?? ""}`}
                  className="border-b border-[var(--glass-border)]/40 hover:bg-[var(--glass-bg)]/50"
                >
                  <td className="px-2 py-1.5 capitalize text-[var(--text-primary)]">
                    {r.provider}
                  </td>
                  <td className="px-2 py-1.5 text-[var(--text-secondary)]">
                    {r.kind}
                  </td>
                  <td className="px-2 py-1.5 font-mono text-[var(--text-muted)]">
                    {r.model ?? "—"}
                  </td>
                  <td className="px-2 py-1.5 text-right font-mono">
                    {r.calls}
                  </td>
                  <td className="px-2 py-1.5 text-right font-mono">
                    {formatTokens(r.prompt_tokens)}
                  </td>
                  <td className="px-2 py-1.5 text-right font-mono">
                    {formatTokens(r.completion_tokens)}
                  </td>
                  <td className="px-2 py-1.5 text-right font-mono">
                    {r.units}
                  </td>
                  <td className="px-2 py-1.5 text-right font-mono text-[var(--text-primary)]">
                    {usd}
                  </td>
                  <td className="px-2 py-1.5 text-right font-mono text-[var(--text-muted)]">
                    {pct}
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
