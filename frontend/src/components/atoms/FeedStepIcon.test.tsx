import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import { FeedStepIcon } from "./FeedStepIcon";

describe("FeedStepIcon", () => {
  it("renders the correct icon for event type", () => {
    const { container } = render(<FeedStepIcon type="ToolCalled" />);
    const icon = container.querySelector("svg");
    expect(icon).toBeInTheDocument();
    expect(container.firstElementChild).toHaveAttribute(
      "data-type",
      "ToolCalled"
    );
  });

  it("adds animate-pulse when isActive", () => {
    const { container } = render(
      <FeedStepIcon type="PlanCreated" isActive />
    );
    const icon = container.querySelector("svg");
    expect(icon?.classList.contains("animate-pulse")).toBe(true);
  });

  it("does not animate when isActive is false", () => {
    const { container } = render(
      <FeedStepIcon type="PlanCreated" isActive={false} />
    );
    const icon = container.querySelector("svg");
    expect(icon?.classList.contains("animate-pulse")).toBe(false);
  });

  it("sets border color based on tone", () => {
    const { container, rerender } = render(
      <FeedStepIcon type="ToolCalled" />
    );
    let badge = container.firstElementChild as HTMLElement;
    const infoColor = badge.style.borderColor;
    expect(infoColor).toBeTruthy();

    // ClaimCovered uses "success" tone, which is different from "info"
    rerender(<FeedStepIcon type="ClaimCovered" />);
    badge = container.firstElementChild as HTMLElement;
    const successColor = badge.style.borderColor;
    expect(successColor).toBeTruthy();
    expect(successColor).not.toBe(infoColor);
  });

  it("merges custom className", () => {
    const { container } = render(
      <FeedStepIcon type="Stopped" className="custom-badge" />
    );
    expect(container.firstElementChild?.className).toContain("custom-badge");
  });

  it("has no a11y violations", async () => {
    const { container } = render(<FeedStepIcon type="EvidenceAdded" />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
