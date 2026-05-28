import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { MetaRow } from "./MetaRow";

describe("MetaRow", () => {
  it("renders owner, format, and threshold for a running run", () => {
    render(
      <MetaRow
        startedAt="2026-05-26T00:00:00Z"
        stoppedAt={null}
        outputFormat="structured"
        confidenceThreshold={0.7}
        ownerUsername="alice"
      />
    );
    expect(screen.getByText("alice")).toBeInTheDocument();
    expect(screen.getByText("Structured")).toBeInTheDocument();
    expect(screen.getByText(/threshold 0\.70/)).toBeInTheDocument();
    expect(screen.queryByTitle("Total elapsed time")).not.toBeInTheDocument();
  });

  it("renders the duration chip once the run has stopped", () => {
    render(
      <MetaRow
        startedAt="2026-05-26T00:00:00Z"
        stoppedAt="2026-05-26T00:00:42Z"
        outputFormat="prose"
        confidenceThreshold={0.4}
        ownerUsername="bob"
      />
    );
    expect(screen.getByText("42s")).toBeInTheDocument();
    expect(screen.getByText("Prose")).toBeInTheDocument();
  });
});
