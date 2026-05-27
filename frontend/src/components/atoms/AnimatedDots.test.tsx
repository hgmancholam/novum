import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnimatedDots } from "./AnimatedDots";

describe("AnimatedDots", () => {
  it("renders three dots with staggered delays", () => {
    const { container } = render(<AnimatedDots />);
    const dots = container.querySelectorAll("span[aria-hidden='true']");
    expect(dots).toHaveLength(3);
    expect((dots[0] as HTMLElement).style.animationDelay).toBe("0ms");
    expect((dots[1] as HTMLElement).style.animationDelay).toBe("150ms");
    expect((dots[2] as HTMLElement).style.animationDelay).toBe("300ms");
  });

  it("exposes a status role with custom label", () => {
    render(<AnimatedDots label="Investigando" />);
    expect(screen.getByRole("status")).toHaveAttribute("aria-label", "Investigando");
  });
});
