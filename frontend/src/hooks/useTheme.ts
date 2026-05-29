/**
 * useTheme — React binding for the persisted light/dark preference (IP-28).
 *
 * The boot script in index.html has already applied the correct
 * `data-theme` to <html> before React mounts; this hook mirrors that
 * value into React state, exposes setters that persist + apply, and
 * syncs across tabs via the `storage` event (BRD-28 AC-05).
 */

import { useCallback, useEffect, useState } from "react";

import {
  THEME_STORAGE_KEY,
  applyThemeToDocument,
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

  return { theme, setTheme, toggle };
}
