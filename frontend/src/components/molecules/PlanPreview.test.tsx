import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";

import { PlanPreview, PLAN_PREVIEW_STEPS } from "./PlanPreview";

describe("PlanPreview", () => {
  it("renders all six prototype steps in order", () => {
    render(<PlanPreview />);
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(6);
    for (let i = 0; i < PLAN_PREVIEW_STEPS.length; i++) {
      expect(items[i]).toHaveTextContent(PLAN_PREVIEW_STEPS[i]!);
    }
  });

  it("includes the 'Novum will:' header and event footer", () => {
    render(<PlanPreview />);
    expect(screen.getByText("Novum will:")).toBeInTheDocument();
    expect(
      screen.getByText("Events will appear below as they happen.")
    ).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<PlanPreview />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
