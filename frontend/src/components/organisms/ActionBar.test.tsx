import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { axe } from "jest-axe";

import { ActionBar } from "./ActionBar";

function setup(overrides: Partial<Parameters<typeof ActionBar>[0]> = {}) {
  const props = {
    status: "running" as const,
    onCancel: vi.fn(),
    isCancelling: false,
    ...overrides,
  };
  render(<ActionBar {...props} />);
  return props;
}

describe("ActionBar", () => {
  it("enables Cancel when running and not cancelling, and calls onCancel on click", () => {
    const props = setup();
    const cancel = screen.getByTestId("cancel-button");
    expect(cancel).not.toBeDisabled();
    fireEvent.click(cancel);
    expect(props.onCancel).toHaveBeenCalledTimes(1);
  });

  it("disables Cancel while cancelling", () => {
    setup({ isCancelling: true });
    expect(screen.getByTestId("cancel-button")).toBeDisabled();
  });

  it("disables Cancel when status is not running", () => {
    setup({ status: "stopped" });
    expect(screen.getByTestId("cancel-button")).toBeDisabled();
  });

  it("disables Cancel when status is undefined (loading)", () => {
    setup({ status: undefined });
    expect(screen.getByTestId("cancel-button")).toBeDisabled();
  });

  it("renders the Fork button disabled with the BRD-15 tooltip", () => {
    setup();
    const fork = screen.getByTestId("fork-button");
    expect(fork).toBeDisabled();
    expect(fork).toHaveAttribute(
      "title",
      "Select a step from the trace (coming soon)"
    );
  });

  it("shows a 'Live' indicator while running and 'Stopped' otherwise", () => {
    const { unmount } = render(
      <ActionBar status="running" onCancel={vi.fn()} isCancelling={false} />
    );
    expect(screen.getByText("Live")).toBeInTheDocument();
    unmount();
    render(
      <ActionBar status="stopped" onCancel={vi.fn()} isCancelling={false} />
    );
    expect(screen.getByText("Stopped")).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    const { container } = render(
      <ActionBar status="running" onCancel={vi.fn()} isCancelling={false} />
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it("does not render the Resume button while the run is running", () => {
    setup({ status: "running", stopReason: null });
    expect(screen.queryByTestId("resume-button")).not.toBeInTheDocument();
  });

  it("renders the Resume button on errored/user_cancelled and forwards clicks", () => {
    const onResume = vi.fn();
    render(
      <ActionBar
        status="stopped"
        stopReason="errored"
        onCancel={vi.fn()}
        isCancelling={false}
        onResume={onResume}
      />
    );
    const btn = screen.getByTestId("resume-button");
    expect(btn).toBeInTheDocument();
    fireEvent.click(btn);
    expect(onResume).toHaveBeenCalledTimes(1);
  });

  it("does NOT render Resume on judge_confirmed or honest_* stops", () => {
    render(
      <ActionBar
        status="stopped"
        stopReason="judge_confirmed"
        onCancel={vi.fn()}
        isCancelling={false}
        onResume={vi.fn()}
      />
    );
    expect(screen.queryByTestId("resume-button")).not.toBeInTheDocument();
  });
});
