import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { ConfidenceBar } from "./ConfidenceBar";

describe("ConfidenceBar", () => {
  it("renders percentage rounded from value", () => {
    render(<ConfidenceBar value={0.756} />);
    expect(screen.getByText("76%")).toBeInTheDocument();
  });

  it("renders default label", () => {
    render(<ConfidenceBar value={0.5} />);
    expect(screen.getByText("Confidence")).toBeInTheDocument();
  });

  it("renders a custom label", () => {
    render(<ConfidenceBar value={0.5} label="Coverage" />);
    expect(screen.getByText("Coverage")).toBeInTheDocument();
  });

  it("hides the label row when showLabel=false", () => {
    render(<ConfidenceBar value={0.5} showLabel={false} />);
    expect(screen.queryByText("Confidence")).not.toBeInTheDocument();
  });

  it("flags passed=true when value >= threshold", () => {
    render(<ConfidenceBar value={0.8} threshold={0.7} />);
    const fill = screen.getByTestId("confidence-fill");
    expect(fill).toHaveAttribute("data-passed", "true");
  });

  it("flags passed=false when value < threshold", () => {
    render(<ConfidenceBar value={0.5} threshold={0.7} />);
    const fill = screen.getByTestId("confidence-fill");
    expect(fill).toHaveAttribute("data-passed", "false");
  });

  it("flips passed exactly at the threshold boundary", () => {
    const { rerender } = render(
      <ConfidenceBar value={0.7} threshold={0.7} />
    );
    expect(screen.getByTestId("confidence-fill")).toHaveAttribute(
      "data-passed",
      "true"
    );
    rerender(<ConfidenceBar value={0.69} threshold={0.7} />);
    expect(screen.getByTestId("confidence-fill")).toHaveAttribute(
      "data-passed",
      "false"
    );
  });

  it("clamps values outside [0,1]", () => {
    const { rerender } = render(<ConfidenceBar value={-1} />);
    expect(screen.getByText("0%")).toBeInTheDocument();
    rerender(<ConfidenceBar value={2} />);
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("sets aria-valuenow on the progressbar", () => {
    render(<ConfidenceBar value={0.42} />);
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "42");
    expect(bar).toHaveAttribute("aria-valuemin", "0");
    expect(bar).toHaveAttribute("aria-valuemax", "100");
  });

  it("renders the threshold marker", () => {
    render(<ConfidenceBar value={0.5} threshold={0.7} />);
    expect(screen.getByTestId("confidence-threshold")).toBeInTheDocument();
  });

  it("has no a11y violations", async () => {
    const { container } = render(<ConfidenceBar value={0.65} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
