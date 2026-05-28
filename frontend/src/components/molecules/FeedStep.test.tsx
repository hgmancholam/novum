import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { FeedStep } from "./FeedStep";

// Helper wrapper for a11y compliance
function renderInList(ui: React.ReactElement) {
  return render(<ol>{ui}</ol>);
}

describe("FeedStep", () => {
  it("renders title and icon", () => {
    renderInList(<FeedStep type="ToolCalled" title="Searched the web" />);
    expect(screen.getByText("Searched the web")).toBeInTheDocument();
    expect(screen.getByRole("listitem")).toHaveAttribute(
      "data-type",
      "ToolCalled"
    );
  });

  it("renders summary when provided", () => {
    renderInList(
      <FeedStep
        type="PlanCreated"
        title="Drafted a plan"
        summary="Breaking down the question"
      />
    );
    expect(screen.getByText("Breaking down the question")).toBeInTheDocument();
  });

  it("does not render summary when omitted", () => {
    const { container } = renderInList(
      <FeedStep type="PlanCreated" title="Drafted a plan" />
    );
    expect(container.textContent).not.toContain("Breaking");
  });

  it("displays deltaMs as seconds", () => {
    renderInList(
      <FeedStep
        type="EvidenceAdded"
        title="Found evidence"
        deltaMs={2345}
      />
    );
    expect(screen.getByText(/\+2\.3s/)).toBeInTheDocument();
  });

  it("marks step as active", () => {
    renderInList(
      <FeedStep
        type="JudgeRuled"
        title="Judging"
        isActive
      />
    );
    expect(screen.getByRole("listitem")).toHaveAttribute("data-active", "true");
  });

  it("renders children slot", () => {
    renderInList(
      <FeedStep type="ToolCalled" title="Search">
        <div data-testid="child-content">Custom child</div>
      </FeedStep>
    );
    expect(screen.getByTestId("child-content")).toBeInTheDocument();
  });

  it("merges custom className", () => {
    renderInList(
      <FeedStep
        type="Stopped"
        title="Done"
        className="custom-step"
      />
    );
    expect(screen.getByRole("listitem").className).toContain("custom-step");
  });

  it("has no a11y violations", async () => {
    const { container } = renderInList(
      <FeedStep type="PlanCreated" title="Drafted a plan" />
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
