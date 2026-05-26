import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { CenterPanelContainer } from "./CenterPanelContainer";
import type { RunResponseDto } from "@/lib/api";

const RUN_ID = "00000000-0000-0000-0000-000000000001";

function makeDto(overrides: Partial<RunResponseDto> = {}): RunResponseDto {
  return {
    id: RUN_ID,
    owner_username: "alice",
    question: "What is dark matter?",
    user_context: null,
    question_type: "factual",
    output_format: "prose",
    confidence_threshold: 0.7,
    started_at: "2026-05-26T00:00:00Z",
    stopped_at: null,
    stop_reason: null,
    parent_run_id: null,
    forked_at_event_id: null,
    ...overrides,
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderWithRouter(children: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/runs/${RUN_ID}`]}>
        <Routes>
          <Route path="/runs/:runId" element={children} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  localStorage.setItem("novum_username", "alice");
  localStorage.setItem("novum_token", "secret-token");
});

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("CenterPanelContainer", () => {
  it("shows the loading spinner while fetching (C1)", async () => {
    fetchMock.mockImplementation(
      () =>
        new Promise<Response>(() => {
          // never resolves
        })
    );
    renderWithRouter(<CenterPanelContainer />);
    expect(screen.getByTestId("center-loading")).toBeInTheDocument();
  });

  it("renders the question and the Researching banner for a running run", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(makeDto()));
    renderWithRouter(<CenterPanelContainer />);
    await waitFor(() => {
      expect(screen.getByTestId("center-panel-view")).toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "What is dark matter?"
    );
    expect(screen.getByTestId("researching-banner")).toBeInTheDocument();
  });

  it("renders the StopReasonCard for a terminal run", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        makeDto({
          stop_reason: "honest_unanswerable",
          stopped_at: "2026-05-26T00:01:00Z",
        })
      )
    );
    renderWithRouter(<CenterPanelContainer />);
    await waitFor(() => {
      expect(screen.getByTestId("stop-reason-card")).toHaveAttribute(
        "data-reason",
        "honest_unanswerable"
      );
    });
  });

  it("renders the error card when the run cannot be loaded", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ code: "NOT_FOUND", message: "missing" }, 404)
    );
    renderWithRouter(<CenterPanelContainer />);
    await waitFor(() => {
      expect(screen.getByTestId("center-error")).toBeInTheDocument();
    });
    const card = screen.getByTestId("stop-reason-card");
    expect(card).toHaveAttribute("data-reason", "errored");
  });

  it("flips status to 'stopped' after clicking Cancel", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(makeDto())); // initial GET
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        makeDto({
          stop_reason: "user_cancelled",
          stopped_at: "2026-05-26T00:02:00Z",
        })
      )
    ); // POST cancel
    fetchMock.mockResolvedValue(
      jsonResponse(
        makeDto({
          stop_reason: "user_cancelled",
          stopped_at: "2026-05-26T00:02:00Z",
        })
      )
    ); // refetch

    renderWithRouter(<CenterPanelContainer />);
    await waitFor(() => {
      expect(screen.getByTestId("researching-banner")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("cancel-button"));

    await waitFor(() => {
      expect(screen.getByTestId("stop-reason-card")).toHaveAttribute(
        "data-reason",
        "user_cancelled"
      );
    });
    expect(screen.queryByTestId("researching-banner")).not.toBeInTheDocument();
  });
});
