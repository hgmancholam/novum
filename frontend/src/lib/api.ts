/**
 * HTTP client wrapper using native fetch.
 * All API calls go through this module for consistency.
 */

import { API_URL } from "./constants";

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
  return api.get<RunListItemDto[]>(`/api/runs?${qs.toString()}`, init);
}
