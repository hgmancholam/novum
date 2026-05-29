/**
 * Unit tests for lib/theme.ts (IP-28 / BRD-28 AC-01, AC-06).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  DEFAULT_THEME,
  SYSTEM_LIGHT_MEDIA_QUERY,
  THEME_STORAGE_KEY,
  applyThemeToDocument,
  getStoredTheme,
  getSystemTheme,
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

describe("getStoredTheme", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns null when storage is empty", () => {
    expect(getStoredTheme()).toBeNull();
  });

  it("returns null for invalid stored values", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "system");
    expect(getStoredTheme()).toBeNull();
  });

  it("returns the persisted value when valid", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "light");
    expect(getStoredTheme()).toBe("light");
  });

  it("returns null when getItem throws", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("denied");
    });
    expect(getStoredTheme()).toBeNull();
  });
});

describe("getSystemTheme", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    // @ts-expect-error — undo monkeypatch
    delete window.matchMedia;
  });

  it("returns 'light' when the OS prefers light", () => {
    window.matchMedia = vi.fn().mockImplementation((q: string) => ({
      matches: q === SYSTEM_LIGHT_MEDIA_QUERY,
      media: q,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })) as unknown as typeof window.matchMedia;
    expect(getSystemTheme()).toBe("light");
  });

  it("returns 'dark' when the OS does not prefer light", () => {
    window.matchMedia = vi.fn().mockImplementation((q: string) => ({
      matches: false,
      media: q,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })) as unknown as typeof window.matchMedia;
    expect(getSystemTheme()).toBe("dark");
  });

  it("returns DEFAULT_THEME when matchMedia is missing", () => {
    // @ts-expect-error — simulate environments without matchMedia
    delete window.matchMedia;
    expect(getSystemTheme()).toBe(DEFAULT_THEME);
  });

  it("returns DEFAULT_THEME when matchMedia throws", () => {
    window.matchMedia = vi.fn().mockImplementation(() => {
      throw new Error("nope");
    }) as unknown as typeof window.matchMedia;
    expect(getSystemTheme()).toBe(DEFAULT_THEME);
  });
});

describe("readStoredTheme priority chain", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    // @ts-expect-error — undo monkeypatch
    delete window.matchMedia;
  });

  it("prefers the persisted value over the system preference", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "dark");
    window.matchMedia = vi.fn().mockImplementation(() => ({
      matches: true, // system says light
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })) as unknown as typeof window.matchMedia;
    expect(readStoredTheme()).toBe("dark");
  });

  it("falls back to the system preference when nothing is stored", () => {
    window.matchMedia = vi.fn().mockImplementation((q: string) => ({
      matches: q === SYSTEM_LIGHT_MEDIA_QUERY,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })) as unknown as typeof window.matchMedia;
    expect(readStoredTheme()).toBe("light");
  });
});
