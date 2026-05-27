import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";

import { TypeDisclosure } from "./TypeDisclosure";

describe("TypeDisclosure", () => {
  it("lists the 5 supported question types (RF-06)", () => {
    render(<TypeDisclosure />);
    for (const label of [
      "Factual",
      "Comparative",
      "Definitional",
      "State-of-the-art",
      "Causal",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("lists the 3 rejected types", () => {
    render(<TypeDisclosure />);
    for (const label of ["Predictive", "Opinion", "Personal data"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<TypeDisclosure />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
