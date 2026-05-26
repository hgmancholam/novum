import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { Badge, type BadgeVariant } from "./Badge";

const variants: BadgeVariant[] = [
  "default",
  "success",
  "warning",
  "error",
  "info",
  "secondary",
];

describe("Badge", () => {
  it("renders children", () => {
    render(<Badge>Hello</Badge>);
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  it.each(variants)("renders %s variant with data attribute", (variant) => {
    render(<Badge variant={variant}>{variant}</Badge>);
    const el = screen.getByText(variant);
    expect(el).toHaveAttribute("data-variant", variant);
  });

  it("applies a distinct className per variant", () => {
    const seen = new Set<string>();
    for (const v of variants) {
      const { unmount, container } = render(<Badge variant={v}>x</Badge>);
      const cls = container.firstElementChild?.className ?? "";
      expect(seen.has(cls)).toBe(false);
      seen.add(cls);
      unmount();
    }
  });

  it("merges custom className", () => {
    render(<Badge className="custom-x">tag</Badge>);
    expect(screen.getByText("tag").className).toMatch(/custom-x/);
  });

  it("has no a11y violations", async () => {
    const { container } = render(<Badge>Accessible</Badge>);
    expect(await axe(container)).toHaveNoViolations();
  });
});
