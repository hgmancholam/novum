/**
 * Unit tests for atoms/ThemeToggleIcon.tsx (IP-28).
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ThemeToggleIcon } from "./ThemeToggleIcon";

describe("ThemeToggleIcon", () => {
  it("renders the Sun icon when theme is 'dark'", () => {
    render(<ThemeToggleIcon theme="dark" />);
    expect(screen.getByTestId("theme-icon-dark")).toBeInTheDocument();
    expect(screen.queryByTestId("theme-icon-light")).not.toBeInTheDocument();
  });

  it("renders the Moon icon when theme is 'light'", () => {
    render(<ThemeToggleIcon theme="light" />);
    expect(screen.getByTestId("theme-icon-light")).toBeInTheDocument();
    expect(screen.queryByTestId("theme-icon-dark")).not.toBeInTheDocument();
  });
});
