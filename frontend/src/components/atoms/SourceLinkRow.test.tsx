import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { SourceLinkRow } from "./SourceLinkRow";

describe("SourceLinkRow", () => {
  const mockUrl = "https://www.example.com/article";
  const mockTitle = "Understanding AI Systems";

  it("renders the title", () => {
    render(<SourceLinkRow url={mockUrl} title={mockTitle} />);
    expect(screen.getByText(mockTitle)).toBeInTheDocument();
  });

  it("extracts and displays hostname without www", () => {
    render(<SourceLinkRow url={mockUrl} title={mockTitle} />);
    expect(screen.getByText(/example\.com/)).toBeInTheDocument();
    expect(screen.queryByText(/www\.example\.com/)).not.toBeInTheDocument();
  });

  it("keeps hostname without www prefix unchanged", () => {
    render(
      <SourceLinkRow url="https://github.com/repo" title="GitHub Repo" />
    );
    expect(screen.getByText(/github\.com/)).toBeInTheDocument();
  });

  it("handles malformed URLs gracefully", () => {
    render(<SourceLinkRow url="not a url" title="Bad URL" />);
    expect(screen.getByText("Bad URL")).toBeInTheDocument();
    expect(screen.getByText(/unknown/)).toBeInTheDocument();
  });

  it("renders as an anchor with target=_blank and rel=noopener noreferrer", () => {
    render(<SourceLinkRow url={mockUrl} title={mockTitle} />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", mockUrl);
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("sets data-source-type when provided", () => {
    render(
      <SourceLinkRow url={mockUrl} title={mockTitle} sourceType="tavily" />
    );
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("data-source-type", "tavily");
  });

  it("includes favicon with correct src", () => {
    const { container } = render(
      <SourceLinkRow url={mockUrl} title={mockTitle} />
    );
    const img = container.querySelector("img");
    expect(img).toHaveAttribute(
      "src",
      "https://www.google.com/s2/favicons?domain=example.com"
    );
    expect(img).toHaveAttribute("alt", "");
  });

  it("merges custom className", () => {
    render(
      <SourceLinkRow
        url={mockUrl}
        title={mockTitle}
        className="custom-source"
      />
    );
    const link = screen.getByRole("link");
    expect(link.className).toContain("custom-source");
  });

  it("has no a11y violations", async () => {
    const { container } = render(
      <SourceLinkRow url={mockUrl} title={mockTitle} />
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
