/**
 * Cost ledger API client (BRD-29 / IP-29).
 *
 * Wraps `GET /api/runs/{runId}/costs` using the shared `api` helper
 * (which prefixes `API_URL` — L-008). Auth headers are merged in
 * AFTER `...init` per L-009 so explicit values always win.
 */

import { api } from "@/lib/api";
import { getAuthHeaders } from "@/lib/auth";
import type { RunCostsResponse } from "@/types/costs";

export async function fetchRunCosts(
  runId: string,
  init?: RequestInit
): Promise<RunCostsResponse> {
  return api.get<RunCostsResponse>(`/api/runs/${runId}/costs`, {
    ...init,
    // eslint-disable-next-line @typescript-eslint/no-misused-spread
    headers: { ...getAuthHeaders(), ...init?.headers },
  });
}
