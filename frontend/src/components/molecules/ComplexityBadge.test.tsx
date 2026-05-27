import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { ComplexityBadge } from "./ComplexityBadge";
import type { ComplexityHint } from "@/types/events";

const hints: ComplexityHint[] = ["trivial", "standard", "deep"];
const expectedLabels: Record<ComplexityHint, string> = {
  trivial: "Quick lookup",
  standard: "Standard research",
  deep: "Deep investigation",
};

describe("ComplexityBadge", () => {
  it.each(hints)("renders %s variant with correct label", (hint) => {
    render(<ComplexityBadge hint={hint} />);
    const label = expectedLabels[hint]!;
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it.each(hints)("has role=status and aria-label for %s", (hint) => {
    const { container } = render(<ComplexityBadge hint={hint} />);
    const badge = container.querySelector('[role="status"]');
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveAttribute("aria-label", expectedLabels[hint]!);
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<ComplexityBadge hint="standard" />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
