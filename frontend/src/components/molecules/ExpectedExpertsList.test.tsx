import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { ExpectedExpertsList } from "./ExpectedExpertsList";

describe("ExpectedExpertsList", () => {
  it("renders nothing when experts array is empty", () => {
    const { container } = render(<ExpectedExpertsList experts={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders header and one expert badge", () => {
    render(<ExpectedExpertsList experts={["medical_researcher"]} />);
    expect(screen.getByText("Looking for sources from:")).toBeInTheDocument();
    expect(screen.getByText("Medical Researcher")).toBeInTheDocument();
  });

  it("renders multiple expert badges with correct formatting", () => {
    render(
      <ExpectedExpertsList
        experts={["database_engineer", "software_architect", "academic"]}
      />
    );
    expect(screen.getByText("Database Engineer")).toBeInTheDocument();
    expect(screen.getByText("Software Architect")).toBeInTheDocument();
    expect(screen.getByText("Academic")).toBeInTheDocument();
  });

  it("has role=list and correct aria-label", () => {
    render(<ExpectedExpertsList experts={["academic"]} />);
    const list = screen.getByRole("list", {
      name: "Expected expert types for this plan",
    });
    expect(list).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    const { container } = render(
      <ExpectedExpertsList experts={["medical_researcher", "academic"]} />
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
