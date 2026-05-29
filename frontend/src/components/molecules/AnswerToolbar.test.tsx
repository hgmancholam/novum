/**
 * AnswerToolbar tests (D-COPY-AND-FORMAT-INLINE).
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useToastStore } from "@/stores/toastStore";

import { AnswerToolbar } from "./AnswerToolbar";

describe("AnswerToolbar", () => {
  const writeText = vi.fn();

  beforeEach(() => {
    writeText.mockReset();
    Object.assign(navigator, {
      clipboard: { writeText: writeText.mockResolvedValue(undefined) },
    });
    useToastStore.getState().reset();
  });

  afterEach(() => {
    useToastStore.getState().reset();
  });

  it("renders a single copy button", () => {
    render(<AnswerToolbar content="hello" viewMode="prose" />);
    expect(screen.getByRole("button", { name: /copy answer/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /copy as markdown/i })).toBeNull();
  });

  it("hides the toggle when no onViewModeChange handler is provided", () => {
    render(<AnswerToolbar content="hello" viewMode="prose" />);
    expect(screen.queryByRole("group", { name: /answer view format/i })).toBeNull();
  });

  it("hides the toggle when showToggle is false", () => {
    render(
      <AnswerToolbar
        content="hello"
        viewMode="prose"
        onViewModeChange={vi.fn()}
        showToggle={false}
      />,
    );
    expect(screen.queryByRole("group", { name: /answer view format/i })).toBeNull();
  });

  it("shows the toggle and emits the new mode on click", () => {
    const handle = vi.fn();
    render(
      <AnswerToolbar
        content="hello"
        viewMode="prose"
        onViewModeChange={handle}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /^structured$/i }));
    expect(handle).toHaveBeenCalledWith("structured");
  });

  it("copies the active content to the clipboard", async () => {
    render(<AnswerToolbar content="# hi" viewMode="prose" />);
    fireEvent.click(screen.getByRole("button", { name: /copy answer/i }));
    await Promise.resolve();
    expect(writeText).toHaveBeenCalledWith("# hi");
  });

  it("copies whatever content prop is provided (structured-mode markdown)", async () => {
    render(<AnswerToolbar content={"## Findings\n- a\n- b"} viewMode="structured" />);
    fireEvent.click(screen.getByRole("button", { name: /copy answer/i }));
    await Promise.resolve();
    expect(writeText).toHaveBeenCalledWith("## Findings\n- a\n- b");
  });
});
