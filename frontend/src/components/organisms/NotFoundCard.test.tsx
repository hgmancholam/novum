import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { NotFoundCard } from "./NotFoundCard";

describe("NotFoundCard", () => {
  it("renders the not-found microcopy with the runId", () => {
    render(
      <MemoryRouter>
        <NotFoundCard runId="abc-123" />
      </MemoryRouter>
    );
    expect(screen.getByText("Run not found")).toBeInTheDocument();
    expect(screen.getByText("abc-123")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /start a new research/i })
    ).toHaveAttribute("href", "/");
  });

  it("falls back to a generic message without runId", () => {
    render(
      <MemoryRouter>
        <NotFoundCard />
      </MemoryRouter>
    );
    expect(
      screen.getByText("We could not find that run.")
    ).toBeInTheDocument();
  });
});
