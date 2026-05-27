/**
 * Unit tests for FormatSelector molecule (BRD-16).
 */
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";

import { FormatSelector } from "./FormatSelector";
import { API_URL } from "@/lib/constants";

const formats = [
  { name: "prose", display: "Prose" },
  { name: "structured", display: "Structured" },
];

const server = setupServer(
  http.get(`${API_URL}/api/formats`, () => {
    return HttpResponse.json({ formats });
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
}

describe("FormatSelector", () => {
  it("renders loading skeleton when isLoading", () => {
    server.use(
      http.get(`${API_URL}/api/formats`, async () => {
        await new Promise(() => {}); // Never resolves
      })
    );

    renderWithQueryClient(
      <FormatSelector value="prose" onChange={vi.fn()} />
    );

    expect(screen.getByLabelText("Loading formats")).toBeInTheDocument();
  });

  it("renders 2 buttons after load", async () => {
    renderWithQueryClient(
      <FormatSelector value="prose" onChange={vi.fn()} />
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Prose" })).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: "Structured" })).toBeInTheDocument();
  });

  it("calls onChange with correct format name on click", async () => {
    const handleChange = vi.fn();
    const user = userEvent.setup();

    renderWithQueryClient(
      <FormatSelector value="prose" onChange={handleChange} />
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Structured" })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Structured" }));

    expect(handleChange).toHaveBeenCalledWith("structured");
  });

  it('active button has aria-pressed="true"', async () => {
    renderWithQueryClient(
      <FormatSelector value="prose" onChange={vi.fn()} />
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Prose" })).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: "Prose" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    expect(screen.getByRole("button", { name: "Structured" })).toHaveAttribute(
      "aria-pressed",
      "false"
    );
  });

  it("uses API_URL prefix (not relative path)", async () => {
    // This test verifies the fetch URL includes API_URL
    let requestUrl = "";
    server.use(
      http.get(`${API_URL}/api/formats`, ({ request }) => {
        requestUrl = request.url;
        return HttpResponse.json({ formats });
      })
    );

    renderWithQueryClient(
      <FormatSelector value="prose" onChange={vi.fn()} />
    );

    await waitFor(() => {
      expect(requestUrl).toContain(API_URL);
    });
  });
});
