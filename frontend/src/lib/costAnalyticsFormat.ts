/**
 * Cost analytics formatting + palette helpers.
 *
 * Recharts cannot read CSS custom properties at runtime, so chart colors
 * live here as resolved hex values that match the design tokens in
 * `index.css` (--accent etc.) and the provider brand palette used by
 * `ProviderIcon`.
 */

export const CHART_COLORS = [
  "#6366f1", // accent
  "#22c55e", // emerald
  "#f59e0b", // amber
  "#ef4444", // rose
  "#06b6d4", // cyan
  "#a855f7", // violet
  "#ec4899", // pink
  "#10b981", // green
] as const;

export const PROVIDER_COLORS: Record<string, string> = {
  anthropic: "#d97757",
  openai: "#10a37f",
  google: "#4285f4",
  github: "#8b949e",
  tavily: "#6366f1",
  wikipedia: "#94a3b8",
  unknown: "#64748b",
};

export const KIND_COLORS: Record<string, string> = {
  llm: "#6366f1",
  search: "#22c55e",
  fetch: "#f59e0b",
  unknown: "#64748b",
};

export function colorForProvider(provider: string): string {
  return PROVIDER_COLORS[provider.toLowerCase()] ?? PROVIDER_COLORS["unknown"] ?? "#64748b";
}

export function colorForKind(kind: string): string {
  return KIND_COLORS[kind.toLowerCase()] ?? KIND_COLORS["unknown"] ?? "#64748b";
}

export function formatUsd(value: number): string {
  if (value === 0) return "$0.00";
  if (value < 0.01) return `$${value.toFixed(4)}`;
  if (value < 1) return `$${value.toFixed(3)}`;
  return `$${value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function formatTokens(value: number): string {
  if (value < 1000) return value.toString();
  if (value < 1_000_000) return `${(value / 1000).toFixed(1)}k`;
  return `${(value / 1_000_000).toFixed(2)}M`;
}

export function formatInt(value: number): string {
  return value.toLocaleString();
}

export function formatShortDate(iso: string): string {
  // iso is "YYYY-MM-DD"
  const [, m, d] = iso.split("-");
  if (!m || !d) return iso;
  return `${m}/${d}`;
}

export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function daysAgoIso(days: number): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - days);
  return d.toISOString().slice(0, 10);
}
