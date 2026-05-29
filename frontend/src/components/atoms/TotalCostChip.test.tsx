import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { axe } from "jest-axe";

import { TotalCostChip } from "./TotalCostChip";

describe("TotalCostChip", () => {
  it("renders formatted USD and tokens", () => {
    render(<TotalCostChip totalUsd={0.0421} tokens={4_300} />);
    expect(screen.getByTestId("total-cost-chip")).toHaveTextContent(
      "$0.0421 · 4.3K"
    );
  });

  it("uses the AC-11 aria-label phrasing", () => {
    render(<TotalCostChip totalUsd={1.23} tokens={1_200_000} />);
    expect(
      screen.getByLabelText(
        "Cost so far: $1.23, 1.2M tokens. Click to open breakdown."
      )
    ).toBeInTheDocument();
  });

  it("renders a loading placeholder", () => {
    render(<TotalCostChip totalUsd={0} tokens={0} loading />);
    const chip = screen.getByTestId("total-cost-chip");
    expect(chip.querySelector(".animate-pulse")).not.toBeNull();
  });

  it("fires click handler", () => {
    const onClick = vi.fn();
    render(<TotalCostChip totalUsd={1} tokens={10} onClick={onClick} />);
    fireEvent.click(screen.getByTestId("total-cost-chip"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("has no accessibility violations", async () => {
    const { container } = render(
      <TotalCostChip totalUsd={1.23} tokens={4_300} />
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
