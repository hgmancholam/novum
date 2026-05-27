import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { axe } from "jest-axe";

import { EventPayloadViewer } from "./EventPayloadViewer";

describe("EventPayloadViewer", () => {
  it("renders a primitive value", () => {
    render(<EventPayloadViewer value={42} />);
    expect(screen.getByTestId("event-payload-viewer")).toHaveTextContent("42");
  });

  it("renders null and booleans", () => {
    const { rerender } = render(<EventPayloadViewer value={null} />);
    expect(screen.getByTestId("event-payload-viewer")).toHaveTextContent(
      "null"
    );
    rerender(<EventPayloadViewer value={true} />);
    expect(screen.getByTestId("event-payload-viewer")).toHaveTextContent(
      "true"
    );
  });

  it("renders an empty array placeholder", () => {
    render(<EventPayloadViewer value={[]} />);
    expect(screen.getByTestId("event-payload-viewer")).toHaveTextContent("[]");
  });

  it("renders an empty object placeholder", () => {
    render(<EventPayloadViewer value={{}} />);
    expect(screen.getByTestId("event-payload-viewer")).toHaveTextContent("{}");
  });

  it("renders a nested object with collapsible top-level keys", () => {
    render(
      <EventPayloadViewer
        value={{
          question_type: "comparative",
          claims: ["a", "b"],
          meta: { count: 2 },
        }}
      />
    );
    const tops = screen.getAllByTestId("payload-toplevel");
    expect(tops).toHaveLength(3);

    const claimsKey = tops.find((el) => el.getAttribute("data-key") === "claims");
    expect(claimsKey).toBeDefined();
    // open by default
    const claimsButton = claimsKey!.querySelector("button");
    expect(claimsButton).toHaveAttribute("aria-expanded", "true");

    // click to collapse
    fireEvent.click(claimsButton!);
    expect(claimsButton).toHaveAttribute("aria-expanded", "false");
    // collapsed shows array-length placeholder
    expect(claimsKey!.textContent).toContain("[2]");
  });

  it("renders array values with comma separators", () => {
    render(<EventPayloadViewer value={[1, 2, 3]} />);
    const node = screen.getByTestId("event-payload-viewer");
    expect(node.textContent).toContain("1");
    expect(node.textContent).toContain("3");
  });

  it("has no accessibility violations", async () => {
    const { container } = render(
      <EventPayloadViewer
        value={{ a: 1, b: { c: 2 }, d: [true, false] }}
      />
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
