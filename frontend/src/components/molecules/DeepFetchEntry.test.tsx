import { render, screen } from "@testing-library/react";
import { axe, toHaveNoViolations } from "jest-axe";
import { describe, expect, it } from "vitest";

import { DeepFetchEntry } from "./DeepFetchEntry";

expect.extend(toHaveNoViolations);

describe("DeepFetchEntry", () => {
  it("renders success microcopy with title, ms and chars", () => {
    render(
      <DeepFetchEntry
        url="https://example.com/article"
        title="The Title"
        fetchMs={812}
        contentLength={4123}
        success
      />,
    );
    expect(
      screen.getByText(/Fetched full page for «The Title» \(812 ms, 4123 chars\)/),
    ).toBeInTheDocument();
  });

  it("falls back to host when title is missing", () => {
    render(
      <DeepFetchEntry
        url="https://example.com/article"
        fetchMs={1}
        contentLength={1}
        success
      />,
    );
    expect(screen.getByText(/example\.com/)).toBeInTheDocument();
  });

  it("renders failure microcopy with reason", () => {
    render(
      <DeepFetchEntry
        url="https://example.com/x"
        title="X"
        fetchMs={0}
        contentLength={0}
        success={false}
        failureReason="Timeout"
      />,
    );
    expect(screen.getByText(/Deep-fetch failed: Timeout/)).toBeInTheDocument();
  });

  it("renders failure with default reason when none provided", () => {
    render(
      <DeepFetchEntry
        url="https://example.com/x"
        fetchMs={0}
        contentLength={0}
        success={false}
      />,
    );
    expect(screen.getByText(/Deep-fetch failed: unknown reason/)).toBeInTheDocument();
  });

  it("has no a11y violations", async () => {
    const { container } = render(
      <DeepFetchEntry
        url="https://example.com/article"
        title="The Title"
        fetchMs={812}
        contentLength={4123}
        success
      />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
