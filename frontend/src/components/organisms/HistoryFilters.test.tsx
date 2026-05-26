import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { axe } from "jest-axe";

import {
  HistoryFilters,
  hasActiveFilters,
} from "./HistoryFilters";

describe("hasActiveFilters", () => {
  it("returns false for empty filters", () => {
    expect(hasActiveFilters({})).toBe(false);
  });

  it("returns false for empty search string", () => {
    expect(hasActiveFilters({ search: "   " })).toBe(false);
  });

  it("returns true when status is set", () => {
    expect(hasActiveFilters({ status: "running" })).toBe(true);
  });

  it("returns true when stopReason is set", () => {
    expect(hasActiveFilters({ stopReason: "judge_confirmed" })).toBe(true);
  });

  it("returns true when search has content", () => {
    expect(hasActiveFilters({ search: "tokyo" })).toBe(true);
  });
});

describe("HistoryFilters", () => {
  it("emits search text on input change", () => {
    const onChange = vi.fn();
    render(<HistoryFilters filters={{}} onChange={onChange} />);
    fireEvent.change(screen.getByPlaceholderText("Search questions…"), {
      target: { value: "tokyo" },
    });
    expect(onChange).toHaveBeenCalledWith({ search: "tokyo" });
  });

  it("clears search key when input becomes empty", () => {
    const onChange = vi.fn();
    render(
      <HistoryFilters filters={{ search: "tokyo" }} onChange={onChange} />
    );
    fireEvent.change(screen.getByPlaceholderText("Search questions…"), {
      target: { value: "" },
    });
    expect(onChange).toHaveBeenCalledWith({});
  });

  it("toggles status pill on click", () => {
    const onChange = vi.fn();
    render(<HistoryFilters filters={{}} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Running" }));
    expect(onChange).toHaveBeenCalledWith({ status: "running" });
  });

  it("removes status when the same pill is clicked again", () => {
    const onChange = vi.fn();
    render(
      <HistoryFilters filters={{ status: "running" }} onChange={onChange} />
    );
    fireEvent.click(screen.getByRole("button", { name: "Running" }));
    expect(onChange).toHaveBeenCalledWith({});
  });

  it("marks active pill with aria-pressed=true", () => {
    render(
      <HistoryFilters filters={{ status: "completed" }} onChange={() => {}} />
    );
    expect(
      screen.getByRole("button", { name: "Completed" })
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("shows Clear filters only when active", () => {
    const { rerender } = render(
      <HistoryFilters filters={{}} onChange={() => {}} />
    );
    expect(
      screen.queryByRole("button", { name: "Clear filters" })
    ).toBeNull();
    rerender(
      <HistoryFilters
        filters={{ status: "running" }}
        onChange={() => {}}
      />
    );
    expect(
      screen.getByRole("button", { name: "Clear filters" })
    ).toBeInTheDocument();
  });

  it("clears all filters on Clear filters click", () => {
    const onChange = vi.fn();
    render(
      <HistoryFilters
        filters={{ status: "running", search: "x" }}
        onChange={onChange}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(onChange).toHaveBeenCalledWith({});
  });

  it("has no a11y violations", async () => {
    const { container } = render(
      <HistoryFilters filters={{}} onChange={() => {}} />
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
