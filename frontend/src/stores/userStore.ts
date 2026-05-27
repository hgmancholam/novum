/**
 * Zustand store for user identity (BRD-04 §4.8).
 *
 * `initialize` is async (verifies the stored token with the backend),
 * so `isVerifying` starts as `true`. Network errors during verification
 * are treated as "assume valid" to support offline use.
 */

import { create } from "zustand";

import {
  clearIdentity,
  getStoredIdentity,
  storeIdentity,
  type UserIdentity,
} from "@/lib/auth";
import { API_URL } from "@/lib/constants";
import { queryClient } from "@/lib/queryClient";
import { useSelectionStore } from "@/stores/selectionStore";

interface UserState {
  user: UserIdentity | null;
  isVerifying: boolean;
  isAuthenticated: boolean;

  initialize: () => Promise<void>;
  register: (username: string) => Promise<void>;
  logout: () => void;
}

export const useUserStore = create<UserState>((set) => ({
  user: null,
  isVerifying: true,
  isAuthenticated: false,

  initialize: async () => {
    const stored = getStoredIdentity();
    if (!stored) {
      set({ user: null, isVerifying: false, isAuthenticated: false });
      return;
    }

    try {
      const response = await fetch(`${API_URL}/api/auth/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(stored),
      });
      const data = (await response.json()) as { valid: boolean };

      if (data.valid) {
        set({ user: stored, isVerifying: false, isAuthenticated: true });
      } else {
        clearIdentity();
        set({ user: null, isVerifying: false, isAuthenticated: false });
      }
    } catch {
      // Network error: assume the stored identity is still valid so
      // offline sessions keep working (BRD-04 §4.8 / IP-04 §6).
      set({ user: stored, isVerifying: false, isAuthenticated: true });
    }
  },

  register: async (username: string) => {
    const response = await fetch(`${API_URL}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username }),
    });

    if (!response.ok) {
      const error = (await response.json().catch(() => ({}))) as {
        detail?: string;
      };
      throw new Error(error.detail ?? "Registration failed");
    }

    const data = (await response.json()) as { username: string; token: string };
    const identity: UserIdentity = {
      username: data.username,
      token: data.token,
    };
    storeIdentity(identity);
    set({ user: identity, isAuthenticated: true });
  },

  logout: () => {
    clearIdentity();
    queryClient.clear();
    useSelectionStore.getState().reset();
    set({ user: null, isAuthenticated: false });
  },
}));
