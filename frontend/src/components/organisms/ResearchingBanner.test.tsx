import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";

import { ResearchingBanner } from "./ResearchingBanner";

describe("ResearchingBanner", () => {
  it("renders the generic activity when no event has arrived yet", () => {
    render(<ResearchingBanner />);
    expect(screen.getByTestId("researching-banner")).toBeInTheDocument();
    expect(screen.getByTestId("researching-activity")).toHaveTextContent(
      "Trabajando en ello",
    );
  });

  it("derives the activity from the latest event", () => {
    render(
      <ResearchingBanner latestEvent={{ type: "PlanCreated", step_index: 2 }} />,
    );
    expect(screen.getByTestId("researching-activity")).toHaveTextContent(
      /plan/i,
    );
  });

  it("renders the step + event count meta line", () => {
    render(
      <ResearchingBanner
        latestEvent={{ type: "ToolCalled", step_index: 3 }}
        eventCount={5}
      />,
    );
    expect(screen.getByTestId("researching-meta")).toHaveTextContent(
      "step 3 · 5 events",
    );
  });

  it("respects an explicit label override", () => {
    render(<ResearchingBanner label="Working" />);
    expect(screen.getByTestId("researching-activity")).toHaveTextContent(
      "Working",
    );
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<ResearchingBanner />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
