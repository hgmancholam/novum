import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";

import { ResearchingBanner } from "./ResearchingBanner";

describe("ResearchingBanner", () => {
  it("renders the default 'Researching…' microcopy and spinner", () => {
    render(<ResearchingBanner />);
    expect(screen.getByTestId("researching-banner")).toBeInTheDocument();
    // Both the spinner (role=status, aria-label) and the visible label exist.
    expect(screen.getAllByText("Researching\u2026").length).toBeGreaterThan(0);
  });

  it("respects a custom label", () => {
    render(<ResearchingBanner label="Working" />);
    expect(screen.getAllByText("Working").length).toBeGreaterThan(0);
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<ResearchingBanner />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
