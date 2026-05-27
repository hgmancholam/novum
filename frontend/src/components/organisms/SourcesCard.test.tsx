/**
 * SourcesCard tests — ui-prototype.md §8 (organisms), testing-policy.md
 */

import { render, screen, within } from "@testing-library/react";
import { axe, toHaveNoViolations } from "jest-axe";
import { describe, expect, it } from "vitest";

import { SourcesCard } from "./SourcesCard";
import type { SourceEntry } from "./SourcesCard";

expect.extend(toHaveNoViolations);

const SOURCES: SourceEntry[] = [
  {
    url: "https://en.wikipedia.org/wiki/Tokyo",
    title: "Tokyo — Wikipedia",
    sourceType: "wikipedia",
    polarity: "supports",
    confidence: 0.9,
  },
  {
    url: "https://www.japan-guide.com/e/e2164.html",
    title: "Japan Guide: Tokyo",
    sourceType: "tavily",
    polarity: "neutral",
    confidence: 0.6,
  },
  {
    url: "https://example.com/contradicting",
    title: "Contradicting claim source",
    sourceType: "tavily",
    polarity: "contradicts",
    confidence: 0.4,
  },
];

describe("SourcesCard", () => {
  it("renders nothing when sources list is empty", () => {
    const { container } = render(<SourcesCard sources={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders the card section when sources are provided", () => {
    render(<SourcesCard sources={SOURCES} />);
    expect(screen.getByTestId("sources-card")).toBeInTheDocument();
  });

  it("shows the heading 'Sources'", () => {
    render(<SourcesCard sources={SOURCES} />);
    expect(
      screen.getByRole("heading", { name: /sources/i })
    ).toBeInTheDocument();
  });

  it("shows the source count badge", () => {
    render(<SourcesCard sources={SOURCES} />);
    // The count badge is inside the header, distinct from row-index numbers.
    const card = screen.getByTestId("sources-card");
    const header = card.querySelector("[id='sources-card-title']")!.closest("div")!;
    expect(header).toHaveTextContent("3");
  });

  it("renders one row per source", () => {
    render(<SourcesCard sources={SOURCES} />);
    expect(screen.getAllByTestId("source-row")).toHaveLength(3);
  });

  it("renders source titles as external links", () => {
    render(<SourcesCard sources={SOURCES} />);
    const link = screen.getByRole("link", { name: /Tokyo — Wikipedia/i });
    expect(link).toHaveAttribute("href", SOURCES[0]!.url);
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("sorts sources by confidence descending (highest first)", () => {
    render(<SourcesCard sources={SOURCES} />);
    const rows = screen.getAllByTestId("source-row");
    // Row 1 must contain the 0.9-confidence source title
    expect(within(rows[0]!).getByRole("link")).toHaveTextContent(
      "Tokyo — Wikipedia"
    );
    // Row 3 must contain the 0.4-confidence source
    expect(within(rows[2]!).getByRole("link")).toHaveTextContent(
      "Contradicting claim source"
    );
  });

  it("shows polarity badge for each source", () => {
    render(<SourcesCard sources={SOURCES} />);
    expect(screen.getByText("Supports")).toBeInTheDocument();
    expect(screen.getByText("Neutral")).toBeInTheDocument();
    expect(screen.getByText("Contradicts")).toBeInTheDocument();
  });

  it("shows confidence percentage for each source", () => {
    render(<SourcesCard sources={SOURCES} />);
    expect(screen.getByText("90%")).toBeInTheDocument();
    expect(screen.getByText("60%")).toBeInTheDocument();
    expect(screen.getByText("40%")).toBeInTheDocument();
  });

  it("renders the hostname (not the full URL) in the meta row", () => {
    render(<SourcesCard sources={SOURCES} />);
    expect(screen.getByText("en.wikipedia.org")).toBeInTheDocument();
    expect(screen.getByText("japan-guide.com")).toBeInTheDocument();
  });

  it("passes accessibility check", async () => {
    const { container } = render(<SourcesCard sources={SOURCES} />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
