import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { Logo } from "./Logo";

describe("Logo", () => {
  it("renders the mark with default accessible name", () => {
    render(<Logo />);
    expect(screen.getByRole("img", { name: "Novum" })).toBeInTheDocument();
  });

  it("renders decoratively when title is empty", () => {
    const { container } = render(<Logo title="" />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg).not.toHaveAttribute("role", "img");
  });

  it("renders the wordmark variant", () => {
    render(<Logo withWordmark />);
    const svg = screen.getByRole("img", { name: "Novum" });
    expect(svg.querySelector("text")?.textContent).toBe("Novum");
  });

  it("scales by the size prop", () => {
    render(<Logo size={48} />);
    const svg = screen.getByRole("img", { name: "Novum" });
    expect(svg).toHaveAttribute("width", "48");
    expect(svg).toHaveAttribute("height", "48");
  });

  it("has no a11y violations", async () => {
    const { container } = render(<Logo />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
