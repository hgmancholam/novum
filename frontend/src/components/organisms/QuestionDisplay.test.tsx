import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";

import { QuestionDisplay } from "./QuestionDisplay";

describe("QuestionDisplay", () => {
  it("renders the question text inside a heading", () => {
    render(<QuestionDisplay question="What is the capital of France?" />);
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent("What is the capital of France?");
  });

  it("has no accessibility violations", async () => {
    const { container } = render(
      <QuestionDisplay question="Does Mars have liquid water?" />
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
