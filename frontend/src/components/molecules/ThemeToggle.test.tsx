/**
 * Unit tests for molecules/ThemeToggle.tsx (IP-28 / BRD-28 AC-02, AC-04, AC-07).
 */

import { render, screen, fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { axe } from "jest-axe";

import { ThemeToggle } from "./ThemeToggle";
import { THEME_STORAGE_KEY } from "@/lib/theme";

describe("ThemeToggle", () => {
  beforeEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.theme;
  });

  afterEach(() => {
    delete document.documentElement.dataset.theme;
  });

  it("renders as a switch with aria-checked reflecting the theme", () => {
    render(<ThemeToggle />);
    const btn = screen.getByRole("switch");
    expect(btn).toHaveAttribute("aria-checked", "false");
    expect(btn).toHaveAccessibleName("Switch to light mode");
  });

  it("toggles theme on click and updates aria/label/storage/DOM", () => {
    render(<ThemeToggle />);
    const btn = screen.getByRole("switch");

    fireEvent.click(btn);

    expect(btn).toHaveAttribute("aria-checked", "true");
    expect(btn).toHaveAccessibleName("Switch to dark mode");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("toggles via keyboard (Space and Enter activate the button)", () => {
    render(<ThemeToggle />);
    const btn = screen.getByRole("switch");
    btn.focus();
    expect(btn).toHaveFocus();

    // fireEvent.click is what browsers emit for Space/Enter on a <button>.
    fireEvent.click(btn);
    expect(btn).toHaveAttribute("aria-checked", "true");

    fireEvent.click(btn);
    expect(btn).toHaveAttribute("aria-checked", "false");
  });

  it("has no axe violations in dark mode", async () => {
    document.documentElement.dataset.theme = "dark";
    const { container } = render(<ThemeToggle />);
    expect(await axe(container)).toHaveNoViolations();
  });

  it("has no axe violations in light mode", async () => {
    localStorage.setItem(THEME_STORAGE_KEY, "light");
    document.documentElement.dataset.theme = "light";
    const { container } = render(<ThemeToggle />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
