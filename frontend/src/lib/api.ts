/**
 * HTTP client wrapper using native fetch.
 * All API calls go through this module for consistency.
 */

import { API_URL } from "./constants";
import { getAuthHeaders } from "./auth";
import type { LlmProviderName } from "./providers";

export interface ApiError {
  code: string;
  message: string;
  details?: unknown;
}

export class ApiClientError extends Error {
  constructor(
    public readonly status: number,
    public readonly error: ApiError
  ) {
    super(error.message);
    this.name = "ApiClientError";
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({
      code: "UNKNOWN_ERROR",
      message: response.statusText,
    }));
    throw new ApiClientError(response.status, error);
  }
  return response.json() as Promise<T>;
}

export const api = {
  async get<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${API_URL}${path}`, {
      method: "GET",
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
    });
    return handleResponse<T>(response);
  },

  async post<T>(path: string, body?: unknown, init?: RequestInit): Promise<T> {
    const response = await fetch(`${API_URL}${path}`, {
      method: "POST",
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
      body: body !== undefined ? JSON.stringify(body) : null,
    });
    return handleResponse<T>(response);
  },

  async put<T>(path: string, body?: unknown, init?: RequestInit): Promise<T> {
    const response = await fetch(`${API_URL}${path}`, {
      method: "PUT",
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
      body: body !== undefined ? JSON.stringify(body) : null,
    });
    return handleResponse<T>(response);
  },

  async delete<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${API_URL}${path}`, {
      method: "DELETE",
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
    });
    return handleResponse<T>(response);
  },
};

// ---------------------------------------------------------------------------
// Typed endpoint wrappers
// ---------------------------------------------------------------------------

export interface RunListItemDto {
  id: string;
  username: string;
  question: string;
  started_at: string;
  stopped_at: string | null;
  stop_reason:
    | "judge_confirmed"
    | "stopped_by_budget"
    | "user_cancelled"
    | "errored"
    | null;
  llm_provider?: string;
}

export interface ListRunsParams {
  limit?: number;
  cursor?: string | null;
}

export interface RunListPageDto {
  items: RunListItemDto[];
  has_more: boolean;
  next_cursor: string | null;
}

export async function listRuns(
  params: ListRunsParams = {},
  init?: RequestInit
): Promise<RunListPageDto> {
  const limit = params.limit ?? 20;
  const qs = new URLSearchParams({ limit: String(limit) });
  if (params.cursor) {
    qs.set("cursor", params.cursor);
  }
  return api.get<RunListPageDto>(`/api/runs?${qs.toString()}`, {
    ...init,
    // eslint-disable-next-line @typescript-eslint/no-misused-spread
    headers: { ...getAuthHeaders(), ...init?.headers },
  });
}

/**
 * DELETE /api/runs/{id} — requires auth, returns 204 No Content.
 *
 * We bypass ``api.delete`` here because that helper assumes a JSON body
 * on every successful response; 204 returns no body and would crash
 * ``response.json()``. The ``...init`` spread MUST come before
 * ``headers`` per L-009 so explicit auth headers always win.
 */
export async function deleteRun(
  runId: string,
  init?: RequestInit
): Promise<void> {
  const response = await fetch(`${API_URL}/api/runs/${runId}`, {
    method: "DELETE",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({
      code: "UNKNOWN_ERROR",
      message: response.statusText,
    }));
    throw new ApiClientError(response.status, error);
  }
}

// ---------------------------------------------------------------------------
// Single run — BRD-13 / IP-13
// ---------------------------------------------------------------------------

export type StopReasonDto =
  | "judge_confirmed"
  | "stopped_by_budget"
  | "user_cancelled"
  | "errored";

export type QuestionTypeDto =
  | "factual"
  | "comparative"
  | "definitional"
  | "state_of_art"
  | "causal";

export type OutputFormatDto = "prose" | "structured";

export interface RunResponseDto {
  id: string;
  owner_username: string;
  question: string;
  user_context: string | null;
  question_type: QuestionTypeDto | null;
  output_format: OutputFormatDto;
  confidence_threshold: number;
  llm_provider: string;
  started_at: string;
  stopped_at: string | null;
  stop_reason: StopReasonDto | null;
  parent_run_id: string | null;
  forked_at_event_id: string | null;
}

/** GET /api/runs/{id} — public, no auth headers. */
export async function getRun(
  runId: string,
  init?: RequestInit
): Promise<RunResponseDto> {
  return api.get<RunResponseDto>(`/api/runs/${runId}`, init);
}

/** POST /api/runs/{id}/cancel — requires X-Username + X-Token (BRD-04). */
export async function cancelRun(
  runId: string,
  init?: RequestInit
): Promise<RunResponseDto> {
  return api.post<RunResponseDto>(`/api/runs/${runId}/cancel`, undefined, {
    ...init,
    headers: { ...getAuthHeaders(), ...init?.headers },
  });
}

/** POST /api/runs/{id}/resume — requires auth (RF-11). */
export async function resumeRun(
  runId: string,
  init?: RequestInit
): Promise<RunResponseDto> {
  return api.post<RunResponseDto>(`/api/runs/${runId}/resume`, undefined, {
    ...init,
    headers: { ...getAuthHeaders(), ...init?.headers },
  });
}

// ---------------------------------------------------------------------------
// Create run — BRD-13 iter 2 (POST /api/runs)
// ---------------------------------------------------------------------------

export interface RunCreatePayload {
  question: string;
  user_context?: string | null;
  output_format?: OutputFormatDto;
  confidence_threshold?: number;
  llm_provider?: LlmProviderName;
}

/** POST /api/runs — requires X-Username + X-Token (BRD-04). */
export async function createRun(
  payload: RunCreatePayload,
  init?: RequestInit
): Promise<RunResponseDto> {
  return api.post<RunResponseDto>("/api/runs", payload, {
    ...init,
    headers: { ...getAuthHeaders(), ...init?.headers },
  });
}

/** POST /api/runs/{id}/fork — requires auth + body { event_id }. */
export async function forkRun(
  runId: string,
  eventId: string,
  init?: RequestInit
): Promise<RunResponseDto> {
  return api.post<RunResponseDto>(
    `/api/runs/${runId}/fork`,
    { event_id: eventId },
    {
      ...init,
      headers: { ...getAuthHeaders(), ...init?.headers },
    }
  );
}
