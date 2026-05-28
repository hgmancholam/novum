import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { axe } from "jest-axe";
import { PlanStepCard, type SubClaim } from "./PlanStepCard";
// Helper wrapper for a11y compliance
function renderInList(ui: React.ReactElement) {
  return render(<ol>{ui}</ol>);
}
describe("PlanStepCard", () => {
  const mockClaims: SubClaim[] = [
    { id: "1", text: "Claim 1", status: "pending" },
    { id: "2", text: "Claim 2", status: "covered" },
    { id: "3", text: "Claim 3", status: "uncoverable" },
  ];

  it("renders title for creation", () => {
    renderInList(
      <PlanStepCard
        rationale="Breaking down the question"
        subClaims={mockClaims}
      />
    );
    expect(screen.getByText("Drafted a plan")).toBeInTheDocument();
  });

  it("renders title for revision", () => {
    renderInList(
      <PlanStepCard
        rationale="Refined approach"
        subClaims={mockClaims}
        isRevision
      />
    );
    expect(screen.getByText("Revised the plan")).toBeInTheDocument();
  });

  it("renders complexity hint when provided", () => {
    renderInList(
      <PlanStepCard
        rationale="Complex question"
        subClaims={mockClaims}
        complexityHint="deep"
      />
    );
    expect(screen.getByText("deep")).toBeInTheDocument();
  });

  it("renders all sub-claims with correct status icons", () => {
    const { container } = renderInList(
      <PlanStepCard
        rationale="Plan rationale"
        subClaims={mockClaims}
      />
    );
    expect(screen.getByText("Claim 1")).toBeInTheDocument();
    expect(screen.getByText("Claim 2")).toBeInTheDocument();
    expect(screen.getByText("Claim 3")).toBeInTheDocument();
    
    // Check that we have 3 icons (one per claim)
    const icons = container.querySelectorAll("svg");
    const claimIcons = Array.from(icons).filter(
      (icon) => icon.getAttribute("width") === "16"
    );
    expect(claimIcons.length).toBeGreaterThanOrEqual(3);
  });

  it("truncates long rationale by default", () => {
    const longRationale = "A".repeat(200);
    const { container } = renderInList(
      <PlanStepCard
        rationale={longRationale}
        subClaims={[]}
      />
    );
    const rationaleEl = container.querySelector("p");
    expect(rationaleEl?.className).toContain("line-clamp-2");
  });

  it("expands rationale when toggle is clicked", async () => {
    const user = userEvent.setup();
    const longRationale = "A".repeat(200);
    const { container } = renderInList(
      <PlanStepCard
        rationale={longRationale}
        subClaims={[]}
      />
    );

    const toggle = screen.getByRole("button", { name: /expand/i });
    await user.click(toggle);

    const rationaleEl = container.querySelector("p");
    expect(rationaleEl?.className).not.toContain("line-clamp-2");
  });

  it("does not show toggle for short rationale", () => {
    renderInList(
      <PlanStepCard
        rationale="Short rationale"
        subClaims={mockClaims}
      />
    );
    expect(
      screen.queryByRole("button", { name: /expand/i })
    ).not.toBeInTheDocument();
  });

  it("has no a11y violations", async () => {
    const { container } = renderInList(
      <PlanStepCard
        rationale="Breaking down the question"
        subClaims={mockClaims}
      />
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
