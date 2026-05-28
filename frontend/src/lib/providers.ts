/**
 * LLM provider catalog — names, labels, and localStorage persistence.
 *
 * The selection survives full-page reloads via localStorage so the user
 * does not have to re-pick the provider on every session.
 */

import { API_URL } from "@/lib/constants";

export const LLM_PROVIDERS = ["github", "openai", "anthropic", "google"] as const;
export type LlmProviderName = (typeof LLM_PROVIDERS)[number];

export const PROVIDER_LABELS: Record<LlmProviderName, string> = {
  github: "GitHub Models",
  openai: "OpenAI GPT",
  anthropic: "Anthropic Claude",
  google: "Google Gemini",
};

export const DEFAULT_PROVIDER: LlmProviderName = "anthropic";
const STORAGE_KEY = "novum:llm_provider";

export interface ProviderInfo {
  name: LlmProviderName;
  available: boolean;
  default_model: string;
}

export interface ProviderListResponse {
  providers: ProviderInfo[];
  default: LlmProviderName;
}

function isProviderName(v: unknown): v is LlmProviderName {
  return (
    typeof v === "string" &&
    (LLM_PROVIDERS as readonly string[]).includes(v)
  );
}

export function getStoredProvider(): LlmProviderName {
  if (typeof window === "undefined") return DEFAULT_PROVIDER;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return isProviderName(raw) ? raw : DEFAULT_PROVIDER;
  } catch {
    return DEFAULT_PROVIDER;
  }
}

export function setStoredProvider(name: LlmProviderName): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, name);
  } catch {
    // Ignore quota / private-mode failures.
  }
}

/** GET /api/llm/providers — public, no auth required. */
export async function fetchProviders(): Promise<ProviderListResponse> {
  const res = await fetch(`${API_URL}/api/llm/providers`);
  if (!res.ok) {
    throw new Error(`Failed to load providers (${res.status})`);
  }
  return (await res.json()) as ProviderListResponse;
}
