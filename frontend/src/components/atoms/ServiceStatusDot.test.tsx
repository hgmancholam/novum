import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { axe } from "jest-axe";

import { ServiceStatusDot } from "./ServiceStatusDot";

describe("ServiceStatusDot", () => {
  it.each([
    ["ok", "bg-(--semantic-success)"],
    ["degraded", "bg-(--semantic-warning)"],
    ["down", "bg-(--semantic-danger)"],
    ["disabled", "bg-(--semantic-neutral)"],
    ["no_key", "bg-(--semantic-neutral)"],
  ] as const)("renders the %s status with the matching colour class", (status, klass) => {
    render(<ServiceStatusDot status={status} />);
    const dot = screen.getByTestId("service-status-dot");
    expect(dot).toHaveAttribute("data-status", status);
    expect(dot.className).toContain(klass);
  });

  it("is hidden from assistive tech (the parent pill carries the label)", () => {
    render(<ServiceStatusDot status="ok" />);
    expect(screen.getByTestId("service-status-dot")).toHaveAttribute(
      "aria-hidden",
      "true",
    );
  });

  it("has no axe violations", async () => {
    const { container } = render(<ServiceStatusDot status="degraded" />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
