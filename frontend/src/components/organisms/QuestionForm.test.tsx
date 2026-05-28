import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { axe } from "jest-axe";

import { QuestionForm } from "./QuestionForm";

beforeEach(() => {
  window.localStorage.clear();
  // Silence the ProviderSelect availability fetch in tests — the
  // component falls back to "all enabled" on failure.
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.reject(new Error("network disabled in test")))
  );
});

function setup(props: Partial<Parameters<typeof QuestionForm>[0]> = {}) {
  const onSubmit = vi.fn();
  render(<QuestionForm onSubmit={onSubmit} {...props} />);
  return { onSubmit };
}

describe("QuestionForm", () => {
  it("disables the submit button until the question is long enough", () => {
    setup();
    const submit = screen.getByTestId("submit-question");
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/your question/i), {
      target: { value: "short" },
    });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/your question/i), {
      target: { value: "This is a long enough question." },
    });
    expect(submit).not.toBeDisabled();
  });

  it("submits the question with defaults (Structured, 0.6 threshold)", () => {
    const { onSubmit } = setup();
    fireEvent.change(screen.getByLabelText(/your question/i), {
      target: { value: "What is event sourcing?" },
    });
    fireEvent.click(screen.getByTestId("submit-question"));
    expect(onSubmit).toHaveBeenCalledWith({
      question: "What is event sourcing?",
      userContext: null,
      outputFormat: "structured",
      confidenceThreshold: 0.6,
      llmProvider: "github",
    });
  });

  it("includes trimmed userContext when the context disclosure is opened", () => {
    const { onSubmit } = setup();
    fireEvent.change(screen.getByLabelText(/your question/i), {
      target: { value: "What is event sourcing?" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: /add context/i })
    );
    fireEvent.change(
      screen.getByPlaceholderText(/Anything Novum should know/i),
      { target: { value: "  audience: senior engineers  " } }
    );
    fireEvent.click(screen.getByTestId("submit-question"));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ userContext: "audience: senior engineers" })
    );
  });

  it("switches to prose + high threshold via Advanced", () => {
    const { onSubmit } = setup();
    fireEvent.change(screen.getByLabelText(/your question/i), {
      target: { value: "Why is the sky blue?" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^advanced/i }));
    fireEvent.click(screen.getByLabelText(/^Prose$/));
    fireEvent.click(screen.getByLabelText(/High \(0\.85\)/));
    fireEvent.click(screen.getByTestId("submit-question"));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        outputFormat: "prose",
        confidenceThreshold: 0.85,
      })
    );
  });

  it("renders the loading copy while submitting", () => {
    setup({ isSubmitting: true });
    expect(screen.getByTestId("submit-question")).toHaveTextContent(
      "Starting…"
    );
  });

  it("surfaces a submitError", () => {
    setup({ submitError: "boom" });
    expect(screen.getByRole("alert")).toHaveTextContent("boom");
  });

  it("seeds the textarea from initialQuestion when empty", () => {
    setup({ initialQuestion: "Seeded question text" });
    expect(screen.getByLabelText(/your question/i)).toHaveValue(
      "Seeded question text"
    );
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<QuestionForm onSubmit={vi.fn()} />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it("defaults the provider to github and submits the chosen value", () => {
    const { onSubmit } = setup();
    const select = screen.getByTestId("provider-select") as HTMLSelectElement;
    expect(select.value).toBe("github");

    fireEvent.change(select, { target: { value: "anthropic" } });
    fireEvent.change(screen.getByLabelText(/your question/i), {
      target: { value: "What is event sourcing?" },
    });
    fireEvent.click(screen.getByTestId("submit-question"));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ llmProvider: "anthropic" })
    );
    expect(window.localStorage.getItem("novum:llm_provider")).toBe("anthropic");
  });

  it("hydrates the selected provider from localStorage", () => {
    window.localStorage.setItem("novum:llm_provider", "openai");
    setup();
    const select = screen.getByTestId("provider-select") as HTMLSelectElement;
    expect(select.value).toBe("openai");
  });
});
