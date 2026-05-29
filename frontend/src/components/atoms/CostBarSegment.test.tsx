import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { CostBarSegment } from "./CostBarSegment";

describe("CostBarSegment", () => {
  it("computes width as (value/total)*100%", () => {
    render(<CostBarSegment provider="tavily" value={25} total={100} color="#f00" />);
    const segment = screen.getByTestId("cost-bar-segment-tavily");
    expect(segment.style.width).toBe("25%");
  });

  it("renders nothing when total is 0", () => {
    const { container } = render(
      <CostBarSegment provider="x" value={5} total={0} color="#f00" />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when value is 0", () => {
    const { container } = render(
      <CostBarSegment provider="x" value={0} total={10} color="#f00" />
    );
    expect(container.firstChild).toBeNull();
  });

  it("is marked as presentation for a11y", () => {
    render(<CostBarSegment provider="x" value={10} total={20} color="#f00" />);
    expect(screen.getByTestId("cost-bar-segment-x").getAttribute("role")).toBe(
      "presentation"
    );
  });
});
