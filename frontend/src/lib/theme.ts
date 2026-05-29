/**
 * Theme helpers (IP-28).
 *
 * Pure functions for reading, writing and applying the user's light/dark
 * preference. All storage and matchMedia access is wrapped in try/catch —
 * private mode, disabled storage, quota errors and missing matchMedia
 * must never reach the React tree.
 *
 * Resolution order (highest priority first):
 *   1. localStorage["novum:theme"]  (explicit user choice — persisted)
 *   2. window.matchMedia("(prefers-color-scheme: light)")  (OS / browser)
 *   3. DEFAULT_THEME ("dark", Slate Aurora identity)
 */

export type Theme = "dark" | "light";

export const THEME_STORAGE_KEY = "novum:theme" as const;
export const DEFAULT_THEME: Theme = "dark";
export const SYSTEM_LIGHT_MEDIA_QUERY = "(prefers-color-scheme: light)" as const;

export function isTheme(value: unknown): value is Theme {
  return value === "dark" || value === "light";
}

/**
 * Returns the explicitly persisted user choice, or `null` if none.
 * `null` means "no opinion yet — fall back to the system / default".
 */
export function getStoredTheme(): Theme | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isTheme(raw) ? raw : null;
  } catch {
    return null;
  }
}

/**
 * Returns the OS / browser preferred theme via `matchMedia`.
 * Falls back to `DEFAULT_THEME` when `matchMedia` is unavailable
 * (SSR, very old browsers, jsdom without polyfill).
 */
export function getSystemTheme(): Theme {
  if (typeof window === "undefined") return DEFAULT_THEME;
  try {
    if (typeof window.matchMedia !== "function") return DEFAULT_THEME;
    return window.matchMedia(SYSTEM_LIGHT_MEDIA_QUERY).matches
      ? "light"
      : "dark";
  } catch {
    return DEFAULT_THEME;
  }
}

/**
 * Resolves the theme to apply now, honoring the priority chain:
 * stored → system → DEFAULT_THEME.
 */
export function readStoredTheme(): Theme {
  return getStoredTheme() ?? getSystemTheme();
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
