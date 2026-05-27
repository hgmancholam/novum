/**
 * HTTP client wrapper using native fetch.
 * All API calls go through this module for consistency.
 */

import { API_URL } from "./constants";
import { getAuthHeaders } from "./auth";

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
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
      ...init,
    });
    return handleResponse<T>(response);
  },

  async post<T>(path: string, body?: unknown, init?: RequestInit): Promise<T> {
    const response = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
      body: body !== undefined ? JSON.stringify(body) : null,
      ...init,
    });
    return handleResponse<T>(response);
  },

  async put<T>(path: string, body?: unknown, init?: RequestInit): Promise<T> {
    const response = await fetch(`${API_URL}${path}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
      body: body !== undefined ? JSON.stringify(body) : null,
      ...init,
    });
    return handleResponse<T>(response);
  },

  async delete<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${API_URL}${path}`, {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
      ...init,
    });
    return handleResponse<T>(response);
  },
};

// ---------------------------------------------------------------------------
// Typed endpoint wrappers
// ---------------------------------------------------------------------------

export interface RunListItemDto {
  id: string;
  question: string;
  started_at: string;
  stopped_at: string | null;
  stop_reason:
    | "judge_confirmed"
    | "honest_unanswerable"
    | "honest_contradiction"
    | "honest_ambiguous"
    | "stopped_by_budget"
    | "user_cancelled"
    | "errored"
    | null;
}

export interface ListRunsParams {
  limit?: number;
  offset?: number;
}

export async function listRuns(
  params: ListRunsParams = {},
  init?: RequestInit
): Promise<RunListItemDto[]> {
  const limit = params.limit ?? 20;
  const offset = params.offset ?? 0;
  const qs = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return api.get<RunListItemDto[]>(`/api/runs?${qs.toString()}`, {
    ...init,
    // eslint-disable-next-line @typescript-eslint/no-misused-spread
    headers: { ...getAuthHeaders(), ...init?.headers },
  });
}

// ---------------------------------------------------------------------------
// Single run — BRD-13 / IP-13
// ---------------------------------------------------------------------------

export type StopReasonDto =
  | "judge_confirmed"
  | "honest_unanswerable"
  | "honest_contradiction"
  | "honest_ambiguous"
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
