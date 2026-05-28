import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { AuthorityTierChip } from "./AuthorityTierChip";

describe("AuthorityTierChip", () => {
  it("renders Primary for primary_authoritative", () => {
    render(<AuthorityTierChip tier="primary_authoritative" />);
    expect(screen.getByRole("status", { name: "Primary" })).toBeInTheDocument();
  });

  it("renders Reputable for reputable_secondary", () => {
    render(<AuthorityTierChip tier="reputable_secondary" />);
    expect(screen.getByRole("status", { name: "Reputable" })).toBeInTheDocument();
  });

  it("renders General for general", () => {
    render(<AuthorityTierChip tier="general" />);
    expect(screen.getByRole("status", { name: "General" })).toBeInTheDocument();
  });

  it("renders Low signal for low_signal", () => {
    render(<AuthorityTierChip tier="low_signal" />);
    expect(screen.getByRole("status", { name: "Low signal" })).toBeInTheDocument();
  });

  it("has no a11y violations across all variants", async () => {
    const { container } = render(
      <>
        <AuthorityTierChip tier="primary_authoritative" />
        <AuthorityTierChip tier="reputable_secondary" />
        <AuthorityTierChip tier="general" />
        <AuthorityTierChip tier="low_signal" />
      </>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
