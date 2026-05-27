import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { axe } from "jest-axe";

import { ForkableEventRow } from "./ForkableEventRow";

describe("ForkableEventRow", () => {
  it("renders type, step index and summary", () => {
    render(
      <ForkableEventRow
        eventId="evt-1"
        type="PlanCreated"
        stepIndex={2}
        summary="Initial plan with 3 steps"
        onSelect={vi.fn()}
      />
    );
    expect(screen.getByText("PlanCreated")).toBeInTheDocument();
    expect(screen.getByText("step 2")).toBeInTheDocument();
    expect(screen.getByText("Initial plan with 3 steps")).toBeInTheDocument();
  });

  it("calls onSelect with the event id when the button is clicked", () => {
    const onSelect = vi.fn();
    render(
      <ForkableEventRow
        eventId="evt-1"
        type="JudgeRuled"
        stepIndex={7}
        onSelect={onSelect}
      />
    );
    fireEvent.click(screen.getByTestId("fork-from-button"));
    expect(onSelect).toHaveBeenCalledWith("evt-1");
  });

  it("disables the button while pending", () => {
    render(
      <ForkableEventRow
        eventId="evt-1"
        type="JudgeRuled"
        stepIndex={7}
        isPending
        onSelect={vi.fn()}
      />
    );
    expect(screen.getByTestId("fork-from-button")).toBeDisabled();
  });

  it("has no accessibility violations", async () => {
    const { container } = render(
      <ul>
        <ForkableEventRow
          eventId="evt-1"
          type="PlanCreated"
          stepIndex={2}
          summary="Initial plan"
          onSelect={vi.fn()}
        />
      </ul>
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
