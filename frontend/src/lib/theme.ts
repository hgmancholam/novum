/**
 * Theme helpers (IP-28).
 *
 * Pure functions for reading, writing and applying the user's light/dark
 * preference. All storage access is wrapped in try/catch — private mode,
 * disabled storage, and quota errors must never reach the React tree.
 */

export type Theme = "dark" | "light";

export const THEME_STORAGE_KEY = "novum:theme" as const;
export const DEFAULT_THEME: Theme = "dark";

export function isTheme(value: unknown): value is Theme {
  return value === "dark" || value === "light";
}

export function readStoredTheme(): Theme {
  if (typeof window === "undefined") return DEFAULT_THEME;
  try {
    const raw = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isTheme(raw) ? raw : DEFAULT_THEME;
  } catch {
    return DEFAULT_THEME;
  }
}

export function writeStoredTheme(theme: Theme): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // Silently swallow QuotaExceededError / SecurityError (private mode).
  }
}

export function applyThemeToDocument(theme: Theme): void {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.theme = theme;
}
