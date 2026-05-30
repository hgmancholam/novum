import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { KpiCard } from "./KpiCard";

describe("KpiCard", () => {
  it("renders label, value and sub", () => {
    render(<KpiCard label="Total cost" value="$1.23" sub="42 calls" />);
    expect(screen.getByText("Total cost")).toBeInTheDocument();
    expect(screen.getByText("$1.23")).toBeInTheDocument();
    expect(screen.getByText("42 calls")).toBeInTheDocument();
  });

  it("uses the provided testId", () => {
    render(<KpiCard label="x" value="y" testId="kpi-foo" />);
    expect(screen.getByTestId("kpi-foo")).toBeInTheDocument();
  });

  it("has no a11y violations", async () => {
    const { container } = render(<KpiCard label="x" value="y" />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
