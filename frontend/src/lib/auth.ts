/**
 * Authentication utilities for localStorage-based identity (BRD-04 §4.7).
 *
 * Token is stored client-side in localStorage; only the SHA-256 hash
 * lives in the database. `getAuthHeaders` returns the headers needed
 * for protected API routes (`X-Username` + `X-Token`).
 */

const STORAGE_KEY_USERNAME = "novum_username";
const STORAGE_KEY_TOKEN = "novum_token";

export interface UserIdentity {
  username: string;
  token: string;
}

/** Read stored identity from localStorage. Returns null if absent. */
export function getStoredIdentity(): UserIdentity | null {
  const username = localStorage.getItem(STORAGE_KEY_USERNAME);
  const token = localStorage.getItem(STORAGE_KEY_TOKEN);
  if (username && token) {
    return { username, token };
  }
  return null;
}

/** Persist identity to localStorage. */
export function storeIdentity(identity: UserIdentity): void {
  localStorage.setItem(STORAGE_KEY_USERNAME, identity.username);
  localStorage.setItem(STORAGE_KEY_TOKEN, identity.token);
}

/** Remove identity from localStorage. */
export function clearIdentity(): void {
  localStorage.removeItem(STORAGE_KEY_USERNAME);
  localStorage.removeItem(STORAGE_KEY_TOKEN);
}

/** Build auth headers for protected API calls. Empty if no identity. */
export function getAuthHeaders(): Record<string, string> {
  const identity = getStoredIdentity();
  if (!identity) {
    return {};
  }
  return {
    "X-Username": identity.username,
    "X-Token": identity.token,
  };
}
