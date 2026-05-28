import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import { BlinkingCursor } from "./BlinkingCursor";

describe("BlinkingCursor", () => {
  it("renders the cursor glyph", () => {
    const { container } = render(<BlinkingCursor />);
    expect(container.textContent).toBe("▌");
  });

  it("has blink animation class", () => {
    const { container } = render(<BlinkingCursor />);
    const span = container.firstElementChild;
    expect(span?.className).toMatch(/animate-\[blink/);
  });

  it("is aria-hidden", () => {
    const { container } = render(<BlinkingCursor />);
    expect(container.firstElementChild).toHaveAttribute("aria-hidden", "true");
  });

  it("merges custom className", () => {
    const { container } = render(<BlinkingCursor className="custom-cursor" />);
    expect(container.firstElementChild?.className).toContain("custom-cursor");
  });

  it("has no a11y violations", async () => {
    const { container } = render(<BlinkingCursor />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
