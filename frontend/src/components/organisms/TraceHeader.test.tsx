import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";

import { TraceHeader } from "./TraceHeader";

describe("TraceHeader", () => {
  it("shows the live indicator only when streaming", () => {
    const { rerender } = render(
      <TraceHeader eventCount={5} isStreaming={true} />
    );
    expect(screen.getByTestId("trace-live-indicator")).toBeInTheDocument();
    rerender(<TraceHeader eventCount={5} isStreaming={false} />);
    expect(screen.queryByTestId("trace-live-indicator")).toBeNull();
  });

  it("pluralizes the event count correctly", () => {
    const { rerender } = render(
      <TraceHeader eventCount={0} isStreaming={false} />
    );
    expect(screen.getByTestId("trace-header")).toHaveTextContent(
      "no events yet"
    );
    rerender(<TraceHeader eventCount={1} isStreaming={false} />);
    expect(screen.getByTestId("trace-header")).toHaveTextContent("1 event");
    rerender(<TraceHeader eventCount={7} isStreaming={false} />);
    expect(screen.getByTestId("trace-header")).toHaveTextContent("7 events");
  });

  it("renders the 'Trace' title", () => {
    render(<TraceHeader eventCount={0} isStreaming={false} />);
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("Trace");
  });

  it("has no accessibility violations", async () => {
    const { container } = render(
      <TraceHeader eventCount={3} isStreaming={true} />
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
