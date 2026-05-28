/**
 * Tests for HowWeWorkPage — Route /how-we-work.
 *
 * Covers:
 *  - Hero, pipeline diagram, lane cards, anatomy of a run, stop reasons, strategy table, CTA all render.
 *  - The diagram exposes a labelled SVG (role="img").
 *  - "Back to Novum" link points at /.
 *  - All seven stop_reason values are present (RF-02).
 *  - The standard lane is highlighted as Novum's pick.
 *  - No jest-axe a11y violations.
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { axe } from "jest-axe";

import HowWeWorkPage from "./HowWeWorkPage";

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/how-we-work"]}>
      <HowWeWorkPage />
    </MemoryRouter>
  );
}

describe("HowWeWorkPage", () => {
  it("renders the hero headline", () => {
    renderPage();
    expect(
      screen.getByRole("heading", { level: 1, name: /research that knows/i })
    ).toBeInTheDocument();
  });

  it("renders the pipeline diagram with an accessible label", () => {
    renderPage();
    const diagram = screen.getByRole("img", {
      name: /novum pipeline/i,
    });
    expect(diagram.tagName.toLowerCase()).toBe("svg");
  });

  it("renders the three lane cards", () => {
    renderPage();
    expect(screen.getByRole("heading", { level: 3, name: "Trivial" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "Standard" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "Deep" })).toBeInTheDocument();
  });

  it("renders the anatomy-of-a-run trace section", () => {
    renderPage();
    expect(
      screen.getByRole("heading", { name: /every step is logged/i })
    ).toBeInTheDocument();
    // Sample steps from the trace
    expect(screen.getByText(/decompose into 3 sub-claims/i)).toBeInTheDocument();
    expect(screen.getAllByText(/judge_confirmed/i).length).toBeGreaterThan(0);
  });

  it("lists every stop_reason value (RF-02)", () => {
    renderPage();
    const reasons = [
      "judge_confirmed",
      "honest_unanswerable",
      "honest_contradiction",
      "honest_ambiguous",
      "stopped_by_budget",
      "user_cancelled",
      "errored",
    ];
    for (const r of reasons) {
      // judge_confirmed appears more than once (also in the trace section)
      expect(screen.getAllByText(r).length).toBeGreaterThan(0);
    }
  });

  it("highlights Novum's Decomp + Retrieval + CoVe row in the comparison table", () => {
    renderPage();
    expect(
      screen.getByText("Decomp + Retrieval + CoVe")
    ).toBeInTheDocument();
  });

  it("renders a 'Back to Novum' link pointing to /", () => {
    renderPage();
    const back = screen.getByRole("link", { name: /back to novum/i });
    expect(back).toHaveAttribute("href", "/");
  });

  it("renders a CTA link 'Open Novum' pointing to /", () => {
    renderPage();
    const open = screen.getByRole("link", { name: /open novum/i });
    expect(open).toHaveAttribute("href", "/");
  });

  it("has no a11y violations", async () => {
    const { container } = renderPage();
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
