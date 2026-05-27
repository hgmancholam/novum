/**
 * Tests for GlassSurface atom — see ui-design.md §2.3.
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { GlassSurface } from "./GlassSurface";

describe("GlassSurface", () => {
  it("renders children inside a div by default", () => {
    render(<GlassSurface>content</GlassSurface>);
    expect(screen.getByText("content").tagName).toBe("DIV");
  });

  it("applies the default variant when none is provided", () => {
    render(<GlassSurface data-testid="surface">x</GlassSurface>);
    const el = screen.getByTestId("surface");
    expect(el).toHaveAttribute("data-variant", "default");
    expect(el.className).toContain("glass");
  });

  it.each([
    ["subtle", "glass-subtle"],
    ["default", "glass"],
    ["strong", "glass-strong"],
  ] as const)("applies the %s variant class", (variant, expectedClass) => {
    render(
      <GlassSurface variant={variant} data-testid="surface">
        x
      </GlassSurface>
    );
    expect(screen.getByTestId("surface").className).toContain(expectedClass);
  });

  it.each(["none", "sm", "md", "lg", "glow"] as const)(
    "applies the %s elevation",
    (elevation) => {
      render(
        <GlassSurface elevation={elevation} data-testid="surface">
          x
        </GlassSurface>
      );
      expect(screen.getByTestId("surface")).toHaveAttribute(
        "data-elevation",
        elevation
      );
    }
  );

  it("renders as a different element when as prop is passed", () => {
    render(
      <GlassSurface as="section" data-testid="surface">
        x
      </GlassSurface>
    );
    expect(screen.getByTestId("surface").tagName).toBe("SECTION");
  });

  it("forwards arbitrary props to the rendered element", () => {
    render(
      <GlassSurface aria-label="panel" data-testid="surface">
        x
      </GlassSurface>
    );
    expect(screen.getByTestId("surface")).toHaveAttribute(
      "aria-label",
      "panel"
    );
  });

  it("merges custom className with variant styles", () => {
    render(
      <GlassSurface className="custom-cls" data-testid="surface">
        x
      </GlassSurface>
    );
    const el = screen.getByTestId("surface");
    expect(el.className).toContain("custom-cls");
    expect(el.className).toContain("glass");
  });

  it("has no accessibility violations", async () => {
    const { container } = render(
      <GlassSurface aria-label="panel">
        <p>accessible content</p>
      </GlassSurface>
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
