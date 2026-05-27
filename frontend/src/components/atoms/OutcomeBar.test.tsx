import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";

import { OutcomeBar } from "./OutcomeBar";

describe("OutcomeBar", () => {
  it("renders neutral by default", () => {
    render(<OutcomeBar />);
    const el = screen.getByTestId("outcome-bar");
    expect(el).toHaveAttribute("data-variant", "neutral");
  });

  it("maps judge_confirmed → success", () => {
    render(<OutcomeBar reason="judge_confirmed" />);
    expect(screen.getByTestId("outcome-bar")).toHaveAttribute(
      "data-variant",
      "success"
    );
  });

  it.each([
    ["stopped_by_budget", "warning"],
    ["user_cancelled", "neutral"],
    ["errored", "error"],
  ] as const)("maps %s → %s", (reason, variant) => {
    render(<OutcomeBar reason={reason} />);
    expect(screen.getByTestId("outcome-bar")).toHaveAttribute(
      "data-variant",
      variant
    );
  });

  it("respects an explicit variant override when no reason is given", () => {
    render(<OutcomeBar variant="error" />);
    expect(screen.getByTestId("outcome-bar")).toHaveAttribute(
      "data-variant",
      "error"
    );
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<OutcomeBar reason="judge_confirmed" />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
