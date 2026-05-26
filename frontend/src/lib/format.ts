/**
 * Formatting utilities for Novum frontend.
 * All timestamp formatting routes through formatRelative().
 * See ui-prototype.md §9.12.
 */

/**
 * Formats a date relative to now.
 * This is the ONLY allowed way to render timestamps in the UI.
 *
 * | Δ (now − date)              | Output                    |
 * |-----------------------------|---------------------------|
 * | < 60 s                      | "just now"                |
 * | < 60 m                      | "<n>m ago"                |
 * | < 24 h                      | "<n>h ago"                |
 * | < 7 d                       | "<n>d ago"                |
 * | ≥ 7 d, same calendar year   | "MMM D" (e.g. "Mar 14")   |
 * | different calendar year     | "MMM D, YYYY"             |
 *
 * @param date - The date to format (Date object or ISO string)
 * @param now - Reference time (defaults to current time)
 * @returns Formatted relative time string
 */
export function formatRelative(
  date: Date | string,
  now: Date = new Date()
): string {
  const d = typeof date === "string" ? new Date(date) : date;
  const diffMs = now.getTime() - d.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  // < 60 seconds
  if (diffSeconds < 60) {
    return "just now";
  }

  // < 60 minutes
  if (diffMinutes < 60) {
    return `${diffMinutes}m ago`;
  }

  // < 24 hours
  if (diffHours < 24) {
    return `${diffHours}h ago`;
  }

  // < 7 days
  if (diffDays < 7) {
    return `${diffDays}d ago`;
  }

  // Format as date
  const months = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
  ];
  const month = months[d.getMonth()];
  const day = d.getDate();
  const year = d.getFullYear();
  const nowYear = now.getFullYear();

  // Same calendar year
  if (year === nowYear) {
    return `${month} ${day}`;
  }

  // Different calendar year
  return `${month} ${day}, ${year}`;
}

/**
 * Formats a date as ISO 8601 string for tooltips.
 * @param date - The date to format
 * @returns ISO 8601 string (e.g. "2025-03-14T09:42:11Z")
 */
export function formatISO(date: Date | string): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return d.toISOString();
}

/**
 * Truncates text to a maximum length with ellipsis.
 * @param text - The text to truncate
 * @param maxLength - Maximum length before truncation
 * @returns Truncated text with "..." if needed
 */
export function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) {
    return text;
  }
  return text.slice(0, maxLength - 1) + "…";
}

/**
 * Formats elapsed time in seconds.
 * @param seconds - Elapsed time in seconds
 * @returns Formatted string (e.g. "42s", "1m 23s")
 */
export function formatElapsed(seconds: number): string {
  if (seconds < 60) {
    return `${Math.round(seconds)}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  return `${minutes}m ${remainingSeconds}s`;
}
