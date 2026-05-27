import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";

import { TraceEmpty, TRACE_EMPTY_MESSAGE } from "./TraceEmpty";

describe("TraceEmpty", () => {
  it("renders the verbatim microcopy from ui-prototype.md §3.3", () => {
    render(<TraceEmpty />);
    expect(screen.getByTestId("trace-empty")).toHaveTextContent(
      TRACE_EMPTY_MESSAGE
    );
    expect(TRACE_EMPTY_MESSAGE).toBe(
      "Trace will appear here when research starts."
    );
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<TraceEmpty />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
