import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { axe } from "jest-axe";
import { SearchStepCard } from "./SearchStepCard";

// Helper wrapper for a11y compliance
function renderInList(ui: React.ReactElement) {
  return render(<ol>{ui}</ol>);
}

describe("SearchStepCard", () => {
  const mockSources = [
    { url: "https://example.com/1", title: "Source 1" },
    { url: "https://example.com/2", title: "Source 2" },
  ];

  it("renders header with query and count", () => {
    renderInList(
      <SearchStepCard query="AI systems" sources={mockSources} />
    );
    expect(screen.getByText(/"AI systems"/)).toBeInTheDocument();
    expect(screen.getByText(/2 results/)).toBeInTheDocument();
  });

  it("renders all sources when count ≤ 3", () => {
    renderInList(
      <SearchStepCard query="test" sources={mockSources} />
    );
    expect(screen.getByText("Source 1")).toBeInTheDocument();
    expect(screen.getByText("Source 2")).toBeInTheDocument();
  });

  it("collapses sources by default when count > 3", () => {
    const manySources = [
      { url: "https://example.com/1", title: "Source 1" },
      { url: "https://example.com/2", title: "Source 2" },
      { url: "https://example.com/3", title: "Source 3" },
      { url: "https://example.com/4", title: "Source 4" },
    ];
    renderInList(<SearchStepCard query="test" sources={manySources} />);
    expect(screen.queryByText("Source 1")).not.toBeInTheDocument();
  });

  it("expands sources when toggle is clicked", async () => {
    const user = userEvent.setup();
    const manySources = [
      { url: "https://example.com/1", title: "Source 1" },
      { url: "https://example.com/2", title: "Source 2" },
      { url: "https://example.com/3", title: "Source 3" },
      { url: "https://example.com/4", title: "Source 4" },
    ];
    renderInList(<SearchStepCard query="test" sources={manySources} />);

    const toggle = screen.getByRole("button", { name: /expand/i });
    await user.click(toggle);

    expect(screen.getByText("Source 1")).toBeInTheDocument();
    expect(screen.getByText("Source 4")).toBeInTheDocument();
  });

  it("renders empty state when sources is empty", () => {
    const { container } = renderInList(
      <SearchStepCard query="test" sources={[]} />
    );
    expect(container.textContent).toContain("0 results");
    expect(screen.queryByText("Sources")).not.toBeInTheDocument();
  });

  it("passes isActive to FeedStep", () => {
    const { container } = renderInList(
      <SearchStepCard query="test" sources={mockSources} isActive />
    );
    // Get the top-level <li> (FeedStep), not the nested source <li>s
    const feedStep = container.querySelector('li[data-type="ToolCalled"]');
    expect(feedStep).toHaveAttribute("data-active", "true");
  });

  it("has no a11y violations", async () => {
    const { container } = renderInList(
      <SearchStepCard query="AI systems" sources={mockSources} />
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
