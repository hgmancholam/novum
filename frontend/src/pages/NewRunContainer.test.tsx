import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { NewRunContainer } from "./NewRunContainer";
import { useUserStore } from "@/stores/userStore";

function renderWithProviders(children: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={children} />
          <Route
            path="/runs/:runId"
            element={<div data-testid="run-page">run page</div>}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.unstubAllGlobals();
  useUserStore.setState({
    user: null,
    isAuthenticated: false,
    isVerifying: false,
  });
  localStorage.clear();
});

describe("NewRunContainer", () => {
  it("submits the question and navigates to /runs/:id on success", async () => {
    useUserStore.setState({
      user: { username: "alice", token: "secret" },
      isAuthenticated: true,
      isVerifying: false,
    });
    localStorage.setItem("novum_username", "alice");
    localStorage.setItem("novum_token", "secret");

    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        id: "22222222-2222-2222-2222-222222222222",
        owner_username: "alice",
        question: "What is event sourcing?",
        user_context: null,
        question_type: null,
        output_format: "structured",
        confidence_threshold: 0.6,
        started_at: "2026-05-26T00:00:00Z",
        stopped_at: null,
        stop_reason: null,
        parent_run_id: null,
        forked_at_event_id: null,
      })
    );

    renderWithProviders(<NewRunContainer />);

    fireEvent.change(screen.getByLabelText(/your question/i), {
      target: { value: "What is event sourcing?" },
    });
    fireEvent.click(screen.getByTestId("submit-question"));

    await waitFor(() => {
      expect(screen.getByTestId("run-page")).toBeInTheDocument();
    });
  });

  it("does NOT submit when anonymous; opens the login modal instead", () => {
    useUserStore.setState({
      user: null,
      isAuthenticated: false,
      isVerifying: false,
    });

    renderWithProviders(<NewRunContainer />);

    fireEvent.change(screen.getByLabelText(/your question/i), {
      target: { value: "What is event sourcing?" },
    });
    fireEvent.click(screen.getByTestId("submit-question"));

    // We never called the network because the auth gate kicked in.
    expect(fetchMock).not.toHaveBeenCalled();
    // No navigation should have happened.
    expect(screen.queryByTestId("run-page")).not.toBeInTheDocument();
  });

  it("renders the SuggestionChips and TypeDisclosure", () => {
    renderWithProviders(<NewRunContainer />);
    expect(screen.getByTestId("suggestion-chips")).toBeInTheDocument();
    expect(screen.getByTestId("type-disclosure")).toBeInTheDocument();
  });

  it("seeds the textarea when a suggestion is picked", () => {
    renderWithProviders(<NewRunContainer />);
    const chip = screen.getAllByRole("button", { name: /What is event sourcing\?/ })[0];
    if (chip === undefined) {
      throw new Error("suggestion chip not rendered");
    }
    fireEvent.click(chip);
    expect(screen.getByLabelText(/your question/i)).toHaveValue(
      "What is event sourcing?"
    );
  });
});
