/**
 * Unit tests for lib/theme.ts (IP-28 / BRD-28 AC-01, AC-06).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  DEFAULT_THEME,
  THEME_STORAGE_KEY,
  applyThemeToDocument,
  isTheme,
  readStoredTheme,
  writeStoredTheme,
} from "./theme";

describe("isTheme", () => {
  it("accepts valid theme strings", () => {
    expect(isTheme("dark")).toBe(true);
    expect(isTheme("light")).toBe(true);
  });

  it("rejects everything else", () => {
    expect(isTheme("")).toBe(false);
    expect(isTheme("system")).toBe(false);
    expect(isTheme(null)).toBe(false);
    expect(isTheme(undefined)).toBe(false);
    expect(isTheme(42)).toBe(false);
    expect(isTheme({})).toBe(false);
  });
});

describe("readStoredTheme", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns DEFAULT_THEME when storage is empty", () => {
    expect(readStoredTheme()).toBe(DEFAULT_THEME);
  });

  it("returns the stored value when valid", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "light");
    expect(readStoredTheme()).toBe("light");
  });

  it("returns DEFAULT_THEME on invalid stored value", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "system");
    expect(readStoredTheme()).toBe(DEFAULT_THEME);
  });

  it("returns DEFAULT_THEME when getItem throws", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("denied");
    });
    expect(readStoredTheme()).toBe(DEFAULT_THEME);
  });
});

describe("writeStoredTheme", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("persists the value to localStorage", () => {
    writeStoredTheme("light");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
  });

  it("does not throw when setItem fails (QuotaExceededError)", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("QuotaExceededError");
    });
    expect(() => {
      writeStoredTheme("dark");
    }).not.toThrow();
  });
});

describe("applyThemeToDocument", () => {
  afterEach(() => {
    delete document.documentElement.dataset.theme;
  });

  it("sets data-theme on the root element", () => {
    applyThemeToDocument("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    applyThemeToDocument("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });
});
