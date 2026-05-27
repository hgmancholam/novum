import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { axe } from "jest-axe";

import { DEFAULT_SUGGESTIONS, SuggestionChips } from "./SuggestionChips";

describe("SuggestionChips", () => {
  it("renders the 3 default suggestions", () => {
    render(<SuggestionChips onPick={vi.fn()} />);
    for (const q of DEFAULT_SUGGESTIONS) {
      expect(screen.getByRole("button", { name: q })).toBeInTheDocument();
    }
  });

  it("calls onPick with the question text on click", () => {
    const onPick = vi.fn();
    render(<SuggestionChips onPick={onPick} />);
    const first = DEFAULT_SUGGESTIONS[0] ?? "";
    fireEvent.click(screen.getByRole("button", { name: first }));
    expect(onPick).toHaveBeenCalledWith(first);
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<SuggestionChips onPick={vi.fn()} />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
