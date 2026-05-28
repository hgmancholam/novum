import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import { FeedRail } from "./FeedRail";

describe("FeedRail", () => {
  it("renders with neutral tone by default", () => {
    const { container } = render(<FeedRail />);
    const rail = container.firstElementChild;
    expect(rail).toHaveAttribute("data-tone", "neutral");
    expect(rail?.className).toContain("bg-[var(--feed-rail)]");
  });

  it("renders with active tone when specified", () => {
    const { container } = render(<FeedRail tone="active" />);
    const rail = container.firstElementChild;
    expect(rail).toHaveAttribute("data-tone", "active");
    expect(rail?.className).toContain("bg-[var(--feed-rail-active)]");
  });

  it("merges custom className", () => {
    const { container } = render(<FeedRail className="custom-rail" />);
    expect(container.firstElementChild?.className).toContain("custom-rail");
  });

  it("is aria-hidden", () => {
    const { container } = render(<FeedRail />);
    expect(container.firstElementChild).toHaveAttribute("aria-hidden", "true");
  });

  it("has no a11y violations", async () => {
    const { container } = render(<FeedRail />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
