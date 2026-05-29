import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { MetaRow } from "./MetaRow";

describe("MetaRow", () => {
  it("renders owner and started chip for a running run", () => {
    render(
      <MetaRow
        startedAt="2026-05-26T00:00:00Z"
        stoppedAt={null}
        ownerUsername="alice"
      />
    );
    expect(screen.getByText("alice")).toBeInTheDocument();
    expect(screen.queryByText("Structured")).not.toBeInTheDocument();
    expect(screen.queryByText(/threshold/)).not.toBeInTheDocument();
    expect(screen.queryByTitle("Total elapsed time")).not.toBeInTheDocument();
  });

  it("renders the duration chip once the run has stopped", () => {
    render(
      <MetaRow
        startedAt="2026-05-26T00:00:00Z"
        stoppedAt="2026-05-26T00:00:42Z"
        ownerUsername="bob"
      />
    );
    expect(screen.getByText("42s")).toBeInTheDocument();
    expect(screen.queryByText("Prose")).not.toBeInTheDocument();
  });
});
