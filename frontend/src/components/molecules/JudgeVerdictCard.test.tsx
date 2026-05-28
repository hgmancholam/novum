import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { JudgeVerdictCard } from "./JudgeVerdictCard";

// Helper wrapper for a11y compliance
function renderInList(ui: React.ReactElement) {
  return render(<ol>{ui}</ol>);
}

describe("JudgeVerdictCard", () => {
  it('renders "Confirmed" badge when passed', () => {
    renderInList(
      <JudgeVerdictCard
        passed={true}
        finalConfidence={0.85}
        threshold={0.7}
        rationale="Answer meets quality threshold"
      />
    );
    expect(screen.getByText("Confirmed")).toBeInTheDocument();
  });

  it('renders "Retry suggested" badge when not passed', () => {
    renderInList(
      <JudgeVerdictCard
        passed={false}
        finalConfidence={0.65}
        threshold={0.7}
        rationale="Below threshold"
      />
    );
    expect(screen.getByText("Retry suggested")).toBeInTheDocument();
  });

  it("displays confidence percentage and threshold", () => {
    renderInList(
      <JudgeVerdictCard
        passed={true}
        finalConfidence={0.85}
        threshold={0.7}
        rationale="Good"
      />
    );
    expect(screen.getByText(/85%/)).toBeInTheDocument();
    expect(screen.getByText(/threshold: 70%/)).toBeInTheDocument();
  });

  it("renders confidence bar with correct width", () => {
    renderInList(
      <JudgeVerdictCard
        passed={true}
        finalConfidence={0.85}
        threshold={0.7}
        rationale="Good"
      />
    );
    const fill = screen.getByTestId("confidence-fill");
    expect(fill.style.width).toBe("85%");
  });

  it("applies success color when passed", () => {
    renderInList(
      <JudgeVerdictCard
        passed={true}
        finalConfidence={0.85}
        threshold={0.7}
        rationale="Good"
      />
    );
    const fill = screen.getByTestId("confidence-fill");
    expect(fill.className).toContain("bg-[var(--semantic-success)]");
  });

  it("applies warning color when not passed", () => {
    renderInList(
      <JudgeVerdictCard
        passed={false}
        finalConfidence={0.65}
        threshold={0.7}
        rationale="Below"
      />
    );
    const fill = screen.getByTestId("confidence-fill");
    expect(fill.className).toContain("bg-[var(--semantic-warning)]");
  });

  it("renders rationale text", () => {
    const rationale = "The answer is well-supported by sources";
    renderInList(
      <JudgeVerdictCard
        passed={true}
        finalConfidence={0.85}
        threshold={0.7}
        rationale={rationale}
      />
    );
    expect(screen.getByText(rationale)).toBeInTheDocument();
  });

  it("has no a11y violations", async () => {
    const { container } = renderInList(
      <JudgeVerdictCard
        passed={true}
        finalConfidence={0.85}
        threshold={0.7}
        rationale="Answer meets quality threshold"
      />
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
