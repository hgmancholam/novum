import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { CenterPanelContainer } from "./CenterPanelContainer";
import type { RunResponseDto } from "@/lib/api";
import type { RunStreamEvent } from "@/types/events";
import type { UseRunStreamResult } from "@/hooks/useRunStream";

const RUN_ID = "00000000-0000-0000-0000-000000000001";

// Mock `useRunStream` so the SSE/EventSource layer is out of scope for these
// page-level tests. Individual tests override the returned events list via
// `streamMock.mockReturnValueOnce({...})`.
const streamMock = vi.fn<() => UseRunStreamResult>(() => emptyStream());

vi.mock("@/hooks/useRunStream", () => ({
  useRunStream: () => streamMock(),
}));

function emptyStream(): UseRunStreamResult {
  return {
    events: [],
    isConnected: false,
    isComplete: false,
    lastEventId: null,
    error: null,
    reconnect: vi.fn(),
    close: vi.fn(),
  };
}

function streamWith(events: RunStreamEvent[]): UseRunStreamResult {
  return {
    ...emptyStream(),
    events,
    isComplete: true,
  };
}

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
    llm_provider: "github",
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
  streamMock.mockReset();
  streamMock.mockImplementation(() => emptyStream());
  vi.stubGlobal("fetch", fetchMock);
  localStorage.setItem("novum_username", "alice");
  localStorage.setItem("novum_token", "secret-token");

  // Mock scrollIntoView for RunFeed (IP-24)
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("CenterPanelContainer", () => {
  it("shows the loading spinner while fetching (C1)", () => {
    fetchMock.mockImplementation(
      () =>
        new Promise<Response>(() => {
          // never resolves
        })
    );
    renderWithRouter(<CenterPanelContainer />);
    expect(screen.getByTestId("center-loading")).toBeInTheDocument();
  });

  it("renders the question and the RunFeed for a running run (IP-24)", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(makeDto()));
    
    // Mock stream with minimal events for RunFeed
    streamMock.mockImplementation(() =>
      streamWith([
        {
          id: "evt-001",
          type: "ToolCalled",
          timestamp_ms: Date.now(),
          payload: { query: "dark matter", tool_name: "web_search" },
        },
        {
          id: "evt-002",
          type: "EvidenceAdded",
          timestamp_ms: Date.now() + 1000,
          payload: {
            source_url: "https://example.com/article",
            source_title: "Understanding Dark Matter",
            chunk_count: 2,
          },
        },
      ])
    );

    renderWithRouter(<CenterPanelContainer />);
    await waitFor(() => {
      expect(screen.getByTestId("center-panel-view")).toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "What is dark matter?"
    );
    expect(screen.getByTestId("run-feed")).toBeInTheDocument();
  });

  it("renders the StopReasonCard for a terminal run", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        makeDto({
          stop_reason: "stopped_by_budget",
          stopped_at: "2026-05-26T00:01:00Z",
        })
      )
    );
    renderWithRouter(<CenterPanelContainer />);
    // Non-actionable terminal reasons (judge_confirmed, stopped_by_budget,
    // honest_*) no longer render a stand-alone card — TrustSummary owns the
    // outcome. Confirm the panel mounted but the card stayed hidden.
    await waitFor(() => {
      expect(screen.getByTestId("center-panel-view")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("stop-reason-card")).not.toBeInTheDocument();
  });

  it("renders the NotFoundCard for a 404 (C13)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ code: "NOT_FOUND", message: "missing" }, 404)
    );
    renderWithRouter(<CenterPanelContainer />);
    await waitFor(() => {
      expect(screen.getByTestId("not-found-card")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("stop-reason-card")).not.toBeInTheDocument();
  });

  it("renders the error card on other errors (5xx)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ code: "INTERNAL", message: "boom" }, 500)
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
    // Wait for the run to load (IP-24: no feed rendered without events)
    await waitFor(() => {
      expect(screen.getByTestId("question-display")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("cancel-button"));

    await waitFor(() => {
      expect(screen.getByTestId("stop-reason-card")).toHaveAttribute(
        "data-reason",
        "user_cancelled"
      );
    });
    expect(screen.queryByTestId("run-feed")).not.toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // IP-15 — fork & resume wiring
  // -------------------------------------------------------------------------

  it("renders the ForkModal for a terminal run with forkable events (IP-15 F6)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        makeDto({
          stop_reason: "judge_confirmed",
          stopped_at: "2026-05-26T00:05:00Z",
        })
      )
    );
    streamMock.mockImplementation(() =>
      streamWith([
        { id: "evt-a", type: "PlanCreated", step_index: 1 },
        { id: "evt-b", type: "ToolCalled", step_index: 2 },
        { id: "evt-c", type: "JudgeRuled", step_index: 7 },
      ])
    );

    renderWithRouter(<CenterPanelContainer />);
    await waitFor(() => {
      expect(screen.getByTestId("fork-count")).toHaveTextContent("2");
    });
    fireEvent.click(screen.getByTestId("fork-button"));
    expect(screen.getByTestId("fork-modal")).toBeInTheDocument();
    const rows = screen.getAllByTestId("forkable-event-row");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveAttribute("data-event-type", "PlanCreated");
    expect(rows[1]).toHaveAttribute("data-event-type", "JudgeRuled");
  });

  it("wires fork flow and posts the right event_id (IP-15 F6)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        makeDto({
          stop_reason: "judge_confirmed",
          stopped_at: "2026-05-26T00:05:00Z",
        })
      )
    );
    streamMock.mockImplementation(() =>
      streamWith([
        { id: "evt-plan", type: "PlanCreated", step_index: 1 },
      ])
    );

    renderWithRouter(<CenterPanelContainer />);
    await waitFor(() => {
      expect(screen.getByTestId("fork-button")).not.toBeDisabled();
    });

    // Capture the POST /fork request.
    const forkedId = "00000000-0000-0000-0000-0000000000ff";
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        makeDto({
          id: forkedId,
          parent_run_id: RUN_ID,
          forked_at_event_id: "evt-plan",
        })
      )
    );
    // Subsequent invalidation refetches (after fork onSuccess).
    fetchMock.mockResolvedValue(
      jsonResponse(
        makeDto({
          stop_reason: "judge_confirmed",
          stopped_at: "2026-05-26T00:05:00Z",
        })
      )
    );

    fireEvent.click(screen.getByTestId("fork-button"));
    fireEvent.click(screen.getByTestId("fork-from-button"));

    await waitFor(() => {
      const forkCall = fetchMock.mock.calls.find(([url]) => {
        return (
          typeof url === "string" && url.includes(`/api/runs/${RUN_ID}/fork`)
        );
      });
      expect(forkCall).toBeDefined();
      const init = forkCall?.[1] as RequestInit | undefined;
      const body: unknown =
        typeof init?.body === "string" ? JSON.parse(init.body) : init?.body;
      expect(body).toEqual({ event_id: "evt-plan" });
    });
  });

  it("shows the post-resume notice and hides RunFeed until a new event arrives (IP-15 §9, IP-24)", async () => {
    fetchMock.mockResolvedValue(jsonResponse(makeDto()));
    streamMock.mockImplementation(() =>
      streamWith([
        { id: "evt-stop", type: "Stopped", step_index: 3 },
        { id: "evt-resume", type: "ResumedAfterCancel", step_index: 4 },
      ])
    );

    renderWithRouter(<CenterPanelContainer />);
    await waitFor(() => {
      expect(screen.getByTestId("post-resume-notice")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("run-feed")).not.toBeInTheDocument();
  });

  it("re-shows the RunFeed once an agent event arrives past the resume anchor (IP-15 §9, IP-24)", async () => {
    fetchMock.mockResolvedValue(jsonResponse(makeDto()));
    streamMock.mockImplementation(() =>
      streamWith([
        { id: "evt-stop", type: "Stopped", step_index: 3 },
        { id: "evt-resume", type: "ResumedAfterCancel", step_index: 4 },
        { id: "evt-tool", type: "ToolCalled", step_index: 5 },
      ])
    );

    renderWithRouter(<CenterPanelContainer />);
    await waitFor(() => {
      expect(screen.getByTestId("run-feed")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("post-resume-notice")).not.toBeInTheDocument();
  });

  it("surfaces the best-effort outcome when the Stopped event carries answer_kind=best_effort (C3 / RF-17)", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(
        makeDto({
          stop_reason: "stopped_by_budget",
          stopped_at: "2026-05-26T00:05:00Z",
        }),
      ),
    );
    streamMock.mockImplementation(() =>
      streamWith([
        {
          id: "evt-stop",
          type: "Stopped",
          step_index: 9,
          stop_reason: "stopped_by_budget",
          answer_kind: "best_effort",
          answer_prose: "Here is the best the agent could assemble.",
        },
      ]),
    );

    renderWithRouter(<CenterPanelContainer />);
    // The single source of truth for the outcome label is the StatusBadge
    // inside RunHeader. The answer card only carries the explanatory banner.
    await waitFor(() => {
      expect(screen.getByTestId("answer-kind-banner")).toHaveTextContent(
        /could not validate this answer/i,
      );
    });
    const header = screen.getByTestId("run-header");
    expect(within(header).getByText(/best-effort answer/i)).toBeInTheDocument();
    expect(screen.getByTestId("structured-answer")).toBeInTheDocument();
  });
});
