import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TemporalSensitivityBadge } from "./TemporalSensitivityBadge";
import type { TemporalSensitivity } from "@/types/events";

describe("TemporalSensitivityBadge", () => {
  it.each<TemporalSensitivity>([
    "static",
    "slow_changing",
    "volatile",
    "realtime",
  ])("renders label for %s", (sensitivity) => {
    render(<TemporalSensitivityBadge sensitivity={sensitivity} />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("uses warning variant for realtime", () => {
    const { container } = render(
      <TemporalSensitivityBadge sensitivity="realtime" />,
    );
    expect(container.textContent).toMatch(/Real-time/i);
  });
});
