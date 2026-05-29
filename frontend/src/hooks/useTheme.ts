/**
 * useTheme — React binding for the persisted light/dark preference (IP-28).
 *
 * The boot script in index.html has already applied the correct
 * `data-theme` to <html> before React mounts; this hook mirrors that
 * value into React state, exposes setters that persist + apply, and
 * keeps it in sync with:
 *  - the `storage` event (cross-tab, BRD-28 AC-05)
 *  - `matchMedia('(prefers-color-scheme: light)')` changes, but **only
 *    while the user has not made an explicit choice**. Once `setTheme` /
 *    `toggle` runs (which writes localStorage), the persisted value
 *    takes priority and OS-level changes are ignored.
 */

import { useCallback, useEffect, useState } from "react";

import {
  SYSTEM_LIGHT_MEDIA_QUERY,
  THEME_STORAGE_KEY,
  applyThemeToDocument,
  getStoredTheme,
  isTheme,
  readStoredTheme,
  writeStoredTheme,
  type Theme,
} from "@/lib/theme";

export interface UseThemeReturn {
  theme: Theme;
  setTheme: (next: Theme) => void;
  toggle: () => void;
}

export function useTheme(): UseThemeReturn {
  const [theme, setThemeState] = useState<Theme>(() => readStoredTheme());

  const setTheme = useCallback((next: Theme): void => {
    writeStoredTheme(next);
    applyThemeToDocument(next);
    setThemeState(next);
  }, []);

  const toggle = useCallback((): void => {
    setThemeState((current) => {
      const next: Theme = current === "dark" ? "light" : "dark";
      writeStoredTheme(next);
      applyThemeToDocument(next);
      return next;
    });
  }, []);

  // Cross-tab sync via the storage event.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const onStorage = (event: StorageEvent): void => {
      if (event.key !== THEME_STORAGE_KEY) return;
      if (!isTheme(event.newValue)) return;
      applyThemeToDocument(event.newValue);
      setThemeState(event.newValue);
    };
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  // Follow OS preference until the user makes an explicit choice.
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (typeof window.matchMedia !== "function") return;
    const mql = window.matchMedia(SYSTEM_LIGHT_MEDIA_QUERY);
    const onChange = (event: MediaQueryListEvent): void => {
      if (getStoredTheme() !== null) return; // persisted choice wins
      const next: Theme = event.matches ? "light" : "dark";
      applyThemeToDocument(next);
      setThemeState(next);
    };
    mql.addEventListener("change", onChange);
    return () => {
      mql.removeEventListener("change", onChange);
    };
  }, []);

  return { theme, setTheme, toggle };
}
