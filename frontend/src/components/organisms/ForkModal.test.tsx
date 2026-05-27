import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { axe } from "jest-axe";

import { ForkModal, type ForkModalEvent } from "./ForkModal";
import { FORK_MODAL_EMPTY_STATE } from "@/lib/microcopy";

const events: ForkModalEvent[] = [
  { id: "evt-1", type: "PlanCreated", stepIndex: 2, summary: "Initial plan" },
  { id: "evt-2", type: "JudgeRuled", stepIndex: 7, summary: "Verdict reached" },
];

describe("ForkModal", () => {
  it("returns null when closed", () => {
    const { container } = render(
      <ForkModal
        isOpen={false}
        events={events}
        onSelect={vi.fn()}
        onClose={vi.fn()}
      />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders rows when there are forkable events", () => {
    render(
      <ForkModal
        isOpen
        events={events}
        onSelect={vi.fn()}
        onClose={vi.fn()}
      />
    );
    expect(screen.getAllByTestId("forkable-event-row")).toHaveLength(2);
    expect(screen.queryByTestId("fork-modal-empty")).not.toBeInTheDocument();
  });

  it("shows the empty state when there are no events", () => {
    render(
      <ForkModal
        isOpen
        events={[]}
        onSelect={vi.fn()}
        onClose={vi.fn()}
      />
    );
    expect(screen.getByTestId("fork-modal-empty")).toHaveTextContent(
      FORK_MODAL_EMPTY_STATE
    );
  });

  it("forwards onSelect with the event id", () => {
    const onSelect = vi.fn();
    render(
      <ForkModal
        isOpen
        events={events}
        onSelect={onSelect}
        onClose={vi.fn()}
      />
    );
    const [firstButton] = screen.getAllByTestId("fork-from-button");
    expect(firstButton).toBeDefined();
    fireEvent.click(firstButton!);
    expect(onSelect).toHaveBeenCalledWith("evt-1");
  });

  it("renders an error message", () => {
    render(
      <ForkModal
        isOpen
        events={events}
        onSelect={vi.fn()}
        onClose={vi.fn()}
        error={new Error("boom")}
      />
    );
    expect(screen.getByTestId("fork-modal-error")).toHaveTextContent("boom");
  });

  it("calls onClose when the Close button is clicked", () => {
    const onClose = vi.fn();
    render(
      <ForkModal
        isOpen
        events={events}
        onSelect={vi.fn()}
        onClose={onClose}
      />
    );
    fireEvent.click(screen.getByTestId("fork-modal-close"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose on Escape key", () => {
    const onClose = vi.fn();
    render(
      <ForkModal
        isOpen
        events={events}
        onSelect={vi.fn()}
        onClose={onClose}
      />
    );
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("disables only the pending row's button while forking", () => {
    render(
      <ForkModal
        isOpen
        events={events}
        onSelect={vi.fn()}
        onClose={vi.fn()}
        isForking
        pendingEventId="evt-2"
      />
    );
    const buttons = screen.getAllByTestId("fork-from-button");
    expect(buttons[0]).not.toBeDisabled();
    expect(buttons[1]).toBeDisabled();
  });

  it("has no accessibility violations", async () => {
    const { container } = render(
      <ForkModal
        isOpen
        events={events}
        onSelect={vi.fn()}
        onClose={vi.fn()}
      />
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
