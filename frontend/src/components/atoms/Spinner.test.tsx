import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { Spinner } from "./Spinner";

describe("Spinner", () => {
  it("renders with role=status", () => {
    render(<Spinner />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("uses default aria-label 'Loading'", () => {
    render(<Spinner />);
    expect(screen.getByRole("status")).toHaveAttribute("aria-label", "Loading");
  });

  it("accepts a custom label", () => {
    render(<Spinner label="Fetching events" />);
    expect(screen.getByRole("status")).toHaveAttribute(
      "aria-label",
      "Fetching events"
    );
  });

  it.each([
    ["sm", "h-4"],
    ["md", "h-6"],
    ["lg", "h-8"],
  ] as const)("applies %s size class", (size, expectedClass) => {
    render(<Spinner size={size} />);
    expect(screen.getByRole("status").className).toMatch(
      new RegExp(expectedClass)
    );
  });

  it("merges custom className", () => {
    render(<Spinner className="extra-class" />);
    expect(screen.getByRole("status").className).toMatch(/extra-class/);
  });

  it("has no a11y violations", async () => {
    const { container } = render(<Spinner />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
