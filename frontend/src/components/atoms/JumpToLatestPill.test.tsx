import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { axe } from "jest-axe";

import { JumpToLatestPill } from "./JumpToLatestPill";

describe("JumpToLatestPill", () => {
  it("renders the verbatim microcopy and aria-label", () => {
    render(<JumpToLatestPill onClick={() => {}} />);
    const btn = screen.getByTestId("jump-to-latest-pill");
    expect(btn).toHaveAttribute("aria-label", "Jump to latest");
    expect(btn).toHaveTextContent("Jump to latest");
  });

  it("invokes onClick", () => {
    const onClick = vi.fn();
    render(<JumpToLatestPill onClick={onClick} />);
    fireEvent.click(screen.getByTestId("jump-to-latest-pill"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<JumpToLatestPill onClick={() => {}} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
