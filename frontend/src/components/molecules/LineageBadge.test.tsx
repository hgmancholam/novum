import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { axe } from "jest-axe";

import { LineageBadge } from "./LineageBadge";
import { LINEAGE_BADGE_LABEL } from "@/lib/microcopy";

describe("LineageBadge", () => {
  it("renders nothing when parentRunId is null", () => {
    const { container } = render(
      <MemoryRouter>
        <LineageBadge parentRunId={null} />
      </MemoryRouter>
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders a link to the parent run when parentRunId is set", () => {
    render(
      <MemoryRouter>
        <LineageBadge parentRunId="run-parent-123" />
      </MemoryRouter>
    );
    const link = screen.getByTestId("lineage-badge");
    expect(link).toHaveAttribute("href", "/runs/run-parent-123");
    expect(link).toHaveTextContent(LINEAGE_BADGE_LABEL);
  });

  it("has no accessibility violations", async () => {
    const { container } = render(
      <MemoryRouter>
        <LineageBadge parentRunId="run-parent-123" />
      </MemoryRouter>
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
