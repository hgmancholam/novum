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

  it("renders complexity badge when complexityHint is provided", () => {
    render(<PlanPreview complexityHint="deep" />);
    expect(screen.getByText("Deep investigation")).toBeInTheDocument();
  });

  it("renders expected experts list when provided", () => {
    render(
      <PlanPreview
        complexityHint="standard"
        expectedExperts={["academic", "medical_researcher"]}
      />
    );
    expect(screen.getByText("Looking for sources from:")).toBeInTheDocument();
    expect(screen.getByText("Academic")).toBeInTheDocument();
    expect(screen.getByText("Medical Researcher")).toBeInTheDocument();
  });

  it("does not render badges when fields are null/undefined", () => {
    render(<PlanPreview complexityHint={null} expectedExperts={null} />);
    expect(screen.queryByText("Quick lookup")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Looking for sources from:")
    ).not.toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<PlanPreview />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
