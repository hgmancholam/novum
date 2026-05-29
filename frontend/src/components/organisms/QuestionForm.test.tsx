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
      llmProvider: "anthropic",
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

  it("submits high threshold via the inline preset (outputFormat is fixed to structured)", () => {
    const { onSubmit } = setup();
    fireEvent.change(screen.getByLabelText(/your question/i), {
      target: { value: "Why is the sky blue?" },
    });
    fireEvent.click(screen.getByLabelText(/High \(0\.85\)/));
    fireEvent.click(screen.getByTestId("submit-question"));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        outputFormat: "structured",
        confidenceThreshold: 0.85,
      })
    );
  });

  it("does not render an Advanced disclosure or a Custom threshold preset", () => {
    setup();
    expect(screen.queryByRole("button", { name: /^advanced/i })).toBeNull();
    expect(screen.queryByLabelText(/^Prose$/)).toBeNull();
    expect(screen.queryByLabelText(/Structured \(recommended\)/i)).toBeNull();
    expect(screen.queryByLabelText(/Custom/i)).toBeNull();
  });

  it("updates the slider value when a preset is clicked and submits that value", () => {
    const { onSubmit } = setup();
    fireEvent.change(screen.getByLabelText(/your question/i), {
      target: { value: "What is event sourcing?" },
    });
    expect(screen.getByTestId("threshold-value")).toHaveTextContent("0.60");
    fireEvent.click(screen.getByLabelText(/Low \(0\.4\)/));
    expect(screen.getByTestId("threshold-value")).toHaveTextContent("0.40");
    fireEvent.change(screen.getByTestId("threshold-slider"), {
      target: { value: "0.75" },
    });
    expect(screen.getByTestId("threshold-value")).toHaveTextContent("0.75");
    fireEvent.click(screen.getByTestId("submit-question"));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ confidenceThreshold: 0.75 })
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

  it("defaults the provider to anthropic and submits the chosen value", () => {
    const { onSubmit } = setup();
    const select = screen.getByTestId("provider-select") as HTMLSelectElement;
    expect(select.value).toBe("anthropic");

    fireEvent.change(select, { target: { value: "openai" } });
    fireEvent.change(screen.getByLabelText(/your question/i), {
      target: { value: "What is event sourcing?" },
    });
    fireEvent.click(screen.getByTestId("submit-question"));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ llmProvider: "openai" })
    );
    expect(window.localStorage.getItem("novum:llm_provider")).toBe("openai");
  });

  it("always starts on the default provider even with a stored value", () => {
    window.localStorage.setItem("novum:llm_provider", "openai");
    setup();
    const select = screen.getByTestId("provider-select") as HTMLSelectElement;
    expect(select.value).toBe("anthropic");
  });
});
