/**
 * CostAnalyticsTable organism — sortable cross-run cost ledger.
 *
 * Stateless: parent passes the rows array. Sort is local-only.
 */

import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, ChevronUp } from "lucide-react";

import { GlassSurface } from "@/components/atoms";
import {
  colorForKind,
  colorForProvider,
  formatTokens,
  formatUsd,
} from "@/lib/costAnalyticsFormat";
import { cn } from "@/lib/cn";
import type { CostRow } from "@/types/costAnalytics";

type SortKey = "occurred_at" | "owner" | "provider" | "kind" | "model" | "tokens" | "cost_usd";
type SortDir = "asc" | "desc";

const COLUMNS: ReadonlyArray<{
  key: SortKey;
  label: string;
  align?: "right";
}> = [
  { key: "occurred_at", label: "When" },
  { key: "owner", label: "User" },
  { key: "provider", label: "Provider" },
  { key: "kind", label: "Kind" },
  { key: "model", label: "Model" },
  { key: "tokens", label: "Tokens", align: "right" },
  { key: "cost_usd", label: "Cost", align: "right" },
];

export interface CostAnalyticsTableProps {
  rows: CostRow[];
  initialSort?: SortKey;
  pageSize?: number;
}

function rowTokens(r: CostRow): number {
  return r.prompt_tokens + r.completion_tokens;
}

function compare(a: CostRow, b: CostRow, key: SortKey): number {
  switch (key) {
    case "occurred_at":
      return a.occurred_at.localeCompare(b.occurred_at);
    case "owner":
      return a.owner.localeCompare(b.owner);
    case "provider":
      return a.provider.localeCompare(b.provider);
    case "kind":
      return a.kind.localeCompare(b.kind);
    case "model":
      return (a.model ?? "").localeCompare(b.model ?? "");
    case "tokens":
      return rowTokens(a) - rowTokens(b);
    case "cost_usd":
      return a.cost_usd - b.cost_usd;
  }
}

export function CostAnalyticsTable({
  rows,
  initialSort = "occurred_at",
  pageSize = 25,
}: CostAnalyticsTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>(initialSort);
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [page, setPage] = useState(0);

  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      const c = compare(a, b, sortKey);
      return sortDir === "asc" ? c : -c;
    });
    return copy;
  }, [rows, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const safePage = Math.min(page, totalPages - 1);
  const pageRows = sorted.slice(safePage * pageSize, (safePage + 1) * pageSize);

  function toggleSort(key: SortKey): void {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
    setPage(0);
  }

  return (
    <GlassSurface
      variant="default"
      elevation="sm"
      radius="lg"
      className="flex flex-col gap-3 p-4"
      data-testid="cost-analytics-table"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-(--text-primary)">
          Cost events
        </h3>
        <span className="text-xs text-(--text-secondary)">
          {sorted.length} row{sorted.length === 1 ? "" : "s"}
        </span>
      </div>

      {sorted.length === 0 ? (
        <p className="py-12 text-center text-sm text-(--text-secondary)">
          No cost events for the selected filters.
        </p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-[var(--glass-border)]">
                  {COLUMNS.map((col) => {
                    const isActive = sortKey === col.key;
                    return (
                      <th
                        key={col.key}
                        scope="col"
                        aria-sort={
                          isActive
                            ? sortDir === "asc"
                              ? "ascending"
                              : "descending"
                            : "none"
                        }
                        className={cn(
                          "px-2 py-2 text-xs font-medium uppercase text-(--text-secondary)",
                          col.align === "right" ? "text-right" : "text-left"
                        )}
                      >
                        <button
                          type="button"
                          onClick={() => { toggleSort(col.key); }}
                          className="inline-flex items-center gap-1 hover:text-(--text-primary)"
                        >
                          {col.label}
                          {isActive ? (
                            sortDir === "asc" ? (
                              <ChevronUp className="h-3 w-3" />
                            ) : (
                              <ChevronDown className="h-3 w-3" />
                            )
                          ) : null}
                        </button>
                      </th>
                    );
                  })}
                  <th scope="col" className="px-2 py-2 text-right text-xs uppercase text-(--text-secondary)">
                    Run
                  </th>
                </tr>
              </thead>
              <tbody>
                {pageRows.map((r, i) => (
                  <tr
                    key={`${r.run_id}-${r.occurred_at}-${i}`}
                    className="border-b border-[var(--glass-border)]/40 hover:bg-(--glass-hover)"
                  >
                    <td className="whitespace-nowrap px-2 py-2 text-xs text-(--text-secondary)">
                      {new Date(r.occurred_at).toLocaleString(undefined, {
                        year: "2-digit",
                        month: "2-digit",
                        day: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                    <td className="px-2 py-2 text-xs text-(--text-secondary)">
                      {r.owner}
                    </td>
                    <td className="px-2 py-2">
                      <span
                        className="inline-block h-2 w-2 rounded-full"
                        style={{ background: colorForProvider(r.provider) }}
                        aria-hidden
                      />{" "}
                      <span className="capitalize">{r.provider}</span>
                    </td>
                    <td className="px-2 py-2">
                      <span
                        className="rounded-full px-2 py-0.5 text-xs uppercase"
                        style={{
                          background: `${colorForKind(r.kind)}22`,
                          color: colorForKind(r.kind),
                        }}
                      >
                        {r.kind}
                      </span>
                    </td>
                    <td className="px-2 py-2 text-xs text-(--text-secondary)">
                      {r.model ?? "—"}
                      {r.task_name ? (
                        <span className="ml-1 text-(--text-tertiary)">
                          · {r.task_name}
                        </span>
                      ) : null}
                    </td>
                    <td className="px-2 py-2 text-right tabular-nums">
                      {formatTokens(rowTokens(r))}
                    </td>
                    <td className="px-2 py-2 text-right tabular-nums">
                      {formatUsd(r.cost_usd)}
                    </td>
                    <td className="px-2 py-2 text-right">
                      <Link
                        to={`/runs/${r.run_id}`}
                        title={r.question}
                        className="text-xs text-(--accent) hover:underline"
                      >
                        Open
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 ? (
            <div className="flex items-center justify-end gap-2 text-xs text-(--text-secondary)">
              <button
                type="button"
                onClick={() => { setPage((p) => Math.max(0, p - 1)); }}
                disabled={safePage === 0}
                className="rounded-md border border-[var(--glass-border)] px-2 py-1 disabled:opacity-50"
              >
                Prev
              </button>
              <span>
                Page {safePage + 1} / {totalPages}
              </span>
              <button
                type="button"
                onClick={() => { setPage((p) => Math.min(totalPages - 1, p + 1)); }}
                disabled={safePage >= totalPages - 1}
                className="rounded-md border border-[var(--glass-border)] px-2 py-1 disabled:opacity-50"
              >
                Next
              </button>
            </div>
          ) : null}
        </>
      )}
    </GlassSurface>
  );
}
