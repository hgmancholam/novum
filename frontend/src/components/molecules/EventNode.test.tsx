import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { axe } from "jest-axe";

import { EventNode, type TraceEventInput } from "./EventNode";

function makeEvent(overrides: Partial<TraceEventInput> = {}): TraceEventInput {
  return {
    key: "id:1",
    type: "PlanCreated",
    stepIndex: 2,
    deltaMs: 800,
    payload: { claims: ["a", "b"] },
    summary: "4 sub-claims",
    ...overrides,
  };
}

describe("EventNode", () => {
  it("renders compact by default (no payload viewer)", () => {
    render(
      <EventNode event={makeEvent()} expanded={false} onToggle={() => {}} />
    );
    const node = screen.getByTestId("event-node");
    expect(node.getAttribute("data-expanded")).toBe("false");
    expect(screen.queryByTestId("event-payload-viewer")).toBeNull();
    expect(node.getAttribute("data-event-type")).toBe("PlanCreated");
    expect(node).toHaveTextContent("Plan");
    expect(node).toHaveTextContent("4 sub-claims");
    expect(node).toHaveTextContent("step 2");
    expect(node).toHaveTextContent("Δ 800 ms");
  });

  it("renders the payload viewer when expanded", () => {
    render(
      <EventNode event={makeEvent()} expanded={true} onToggle={() => {}} />
    );
    expect(screen.getByTestId("event-payload-viewer")).toBeInTheDocument();
  });

  it("toggles aria-expanded and calls onToggle with the event key", () => {
    const onToggle = vi.fn();
    render(
      <EventNode
        event={makeEvent({ key: "id:abc" })}
        expanded={false}
        onToggle={onToggle}
      />
    );
    const btn = within(screen.getByTestId("event-node")).getByRole("button");
    expect(btn).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(btn);
    expect(onToggle).toHaveBeenCalledWith("id:abc");
  });

  it("renders the fork slot only when one is provided", () => {
    const { rerender } = render(
      <EventNode event={makeEvent()} expanded={false} onToggle={() => {}} />
    );
    expect(screen.queryByTestId("event-fork-slot")).toBeNull();
    rerender(
      <EventNode
        event={makeEvent()}
        expanded={false}
        onToggle={() => {}}
        forkSlot={<span>fork</span>}
      />
    );
    expect(screen.getByTestId("event-fork-slot")).toBeInTheDocument();
  });

  it("marks decision events on a data attribute", () => {
    render(
      <EventNode event={makeEvent({ type: "JudgeRuled" })} expanded={false} onToggle={() => {}} />
    );
    expect(screen.getByTestId("event-node").getAttribute("data-decision")).toBe(
      "true"
    );
  });

  it("renders without summary or meta when neither is provided", () => {
    render(
      <EventNode
        event={{
          key: "idx:0",
          type: "Stopped",
          payload: {},
        }}
        expanded={false}
        onToggle={() => {}}
      />
    );
    expect(screen.getByTestId("event-node")).toHaveTextContent("Stopped");
  });

  it("has no accessibility violations", async () => {
    const { container } = render(
      <ol>
        <EventNode event={makeEvent()} expanded={true} onToggle={() => {}} />
      </ol>
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
