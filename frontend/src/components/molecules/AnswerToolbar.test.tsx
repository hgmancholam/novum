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

  it("renders both copy buttons", () => {
    render(
      <AnswerToolbar markdownSource="# hi" viewMode="prose" />
    );
    expect(screen.getByRole("button", { name: /copy answer/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /copy as markdown/i })).toBeInTheDocument();
  });

  it("hides the toggle when no onViewModeChange handler is provided", () => {
    render(<AnswerToolbar markdownSource="# hi" viewMode="prose" />);
    expect(screen.queryByRole("group", { name: /answer view format/i })).toBeNull();
  });

  it("hides the toggle when showToggle is false", () => {
    render(
      <AnswerToolbar
        markdownSource="# hi"
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
        markdownSource="# hi"
        viewMode="prose"
        onViewModeChange={handle}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /^structured$/i }));
    expect(handle).toHaveBeenCalledWith("structured");
  });

  it("copies plain text (fallback to markdownSource when plainText is omitted)", async () => {
    render(<AnswerToolbar markdownSource="# hi" viewMode="prose" />);
    fireEvent.click(screen.getByRole("button", { name: /copy answer/i }));
    await Promise.resolve();
    expect(writeText).toHaveBeenCalledWith("# hi");
  });

  it("prefers plainText over markdownSource for the plain copy", async () => {
    render(
      <AnswerToolbar
        markdownSource="# hi"
        plainText="hi plain"
        viewMode="prose"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /copy answer/i }));
    await Promise.resolve();
    expect(writeText).toHaveBeenCalledWith("hi plain");
  });

  it("copies the markdown source for the markdown button", async () => {
    render(
      <AnswerToolbar
        markdownSource="# raw md"
        plainText="raw md"
        viewMode="prose"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /copy as markdown/i }));
    await Promise.resolve();
    expect(writeText).toHaveBeenCalledWith("# raw md");
  });
});
