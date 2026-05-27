/**
 * Unit tests for StructuredAnswer organism (BRD-16).
 */
import { render, screen } from "@testing-library/react";
import { axe, toHaveNoViolations } from "jest-axe";
import { describe, expect, it } from "vitest";

import { StructuredAnswer } from "./StructuredAnswer";

expect.extend(toHaveNoViolations);

describe("StructuredAnswer", () => {
  it("renders content as markdown", () => {
    render(
      <StructuredAnswer
        content="## Hello\n\nThis is a test."
        outputFormat="prose"
      />
    );

    // ReactMarkdown in JSDOM may include trailing text in the heading accessible name
    expect(screen.getByRole("heading", { name: /Hello/ })).toBeInTheDocument();
    expect(screen.getByTestId("answer-content")).toHaveTextContent("This is a test.");
  });

  it("shows metadata bar when metadata provided", () => {
    render(
      <StructuredAnswer
        content="Test content"
        outputFormat="structured"
        metadata={{ sections: 3, source_count: 5 }}
      />
    );

    const metadata = screen.getByTestId("answer-metadata");
    expect(metadata).toHaveTextContent("3 sections");
    expect(metadata).toHaveTextContent("5 sources");
  });

  it("shows word_count in metadata", () => {
    render(
      <StructuredAnswer
        content="Test"
        outputFormat="prose"
        metadata={{ word_count: 42 }}
      />
    );

    const metadata = screen.getByTestId("answer-metadata");
    expect(metadata).toHaveTextContent("42 words");
  });

  it("no metadata bar when no metadata provided", () => {
    render(
      <StructuredAnswer
        content="Test content"
        outputFormat="prose"
      />
    );

    expect(screen.queryByTestId("answer-metadata")).not.toBeInTheDocument();
  });

  it("no metadata bar when metadata is empty object", () => {
    render(
      <StructuredAnswer
        content="Test content"
        outputFormat="prose"
        metadata={{}}
      />
    );

    expect(screen.queryByTestId("answer-metadata")).not.toBeInTheDocument();
  });

  it('data-testid="structured-answer" present', () => {
    render(
      <StructuredAnswer
        content="Test"
        outputFormat="prose"
      />
    );

    expect(screen.getByTestId("structured-answer")).toBeInTheDocument();
  });

  it('data-testid="answer-content" present', () => {
    render(
      <StructuredAnswer
        content="Test"
        outputFormat="prose"
      />
    );

    expect(screen.getByTestId("answer-content")).toBeInTheDocument();
  });

  it("renders markdown links correctly", () => {
    render(
      <StructuredAnswer
        content="[Example](https://example.com)"
        outputFormat="prose"
      />
    );

    const link = screen.getByRole("link", { name: "Example" });
    expect(link).toHaveAttribute("href", "https://example.com");
  });

  it("has no accessibility violations", async () => {
    const { container } = render(
      <StructuredAnswer
        content="## Heading\n\nParagraph text."
        outputFormat="structured"
        metadata={{ sections: 1 }}
      />
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
