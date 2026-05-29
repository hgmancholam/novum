/**
 * Cost / token formatting helpers (BRD-29 / IP-29).
 *
 * Pure functions, no React. Render strings stay English (code-language
 * policy: UI fallback strings are English).
 */

/**
 * Format a USD amount.
 *   < $1     → 4 decimals ("$0.0421")
 *   >= $1    → 2 decimals ("$1.23")
 *   NaN / ±∞ → "—"
 */
export function formatUsd(value: number): string {
  if (!Number.isFinite(value)) {
    return "—";
  }
  const abs = Math.abs(value);
  const decimals = abs < 1 ? 4 : 2;
  return `$${value.toFixed(decimals)}`;
}

/**
 * Compact token counts.
 *   < 1,000           → exact ("847")
 *   1K..1M            → "4.3K"
 *   >= 1M             → "1.2M"
 */
export function formatTokens(n: number): string {
  if (!Number.isFinite(n)) {
    return "—";
  }
  const v = Math.trunc(n);
  if (Math.abs(v) >= 1_000_000) {
    return `${(v / 1_000_000).toFixed(1)}M`;
  }
  if (Math.abs(v) >= 1_000) {
    return `${(v / 1_000).toFixed(1)}K`;
  }
  return v.toString();
}

/** Percentage with one decimal ("12.4%"). */
export function formatPct(p: number): string {
  if (!Number.isFinite(p)) {
    return "—";
  }
  return `${p.toFixed(1)}%`;
}
