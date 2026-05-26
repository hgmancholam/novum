/**
 * Unit tests for stores/userStore.ts (BRD-04 §4.8).
 *
 * Network is mocked via `vi.spyOn(globalThis, "fetch")` (IP-04 §5.8 —
 * MSW is deferred to a later BRD).
 */

import { act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useUserStore } from "./userStore";

const RESET_STATE = {
  user: null,
  isVerifying: true,
  isAuthenticated: false,
};

function mockFetchOnce(status: number, body: unknown): void {
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

describe("userStore", () => {
  beforeEach(() => {
    localStorage.clear();
    useUserStore.setState({ ...RESET_STATE });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("initialize", () => {
    it("sets unauthenticated state when nothing is stored", async () => {
      await act(async () => {
        await useUserStore.getState().initialize();
      });

      const state = useUserStore.getState();
      expect(state.user).toBeNull();
      expect(state.isVerifying).toBe(false);
      expect(state.isAuthenticated).toBe(false);
    });

    it("keeps the stored identity when the backend confirms it", async () => {
      localStorage.setItem("novum_username", "alice");
      localStorage.setItem("novum_token", "tok");
      mockFetchOnce(200, { valid: true });

      await act(async () => {
        await useUserStore.getState().initialize();
      });

      const state = useUserStore.getState();
      expect(state.user).toEqual({ username: "alice", token: "tok" });
      expect(state.isAuthenticated).toBe(true);
      expect(state.isVerifying).toBe(false);
    });

    it("clears the stored identity when the backend rejects it", async () => {
      localStorage.setItem("novum_username", "alice");
      localStorage.setItem("novum_token", "tok");
      mockFetchOnce(200, { valid: false });

      await act(async () => {
        await useUserStore.getState().initialize();
      });

      const state = useUserStore.getState();
      expect(state.user).toBeNull();
      expect(state.isAuthenticated).toBe(false);
      expect(localStorage.getItem("novum_username")).toBeNull();
      expect(localStorage.getItem("novum_token")).toBeNull();
    });

    it("keeps the stored identity on network error (offline support)", async () => {
      localStorage.setItem("novum_username", "alice");
      localStorage.setItem("novum_token", "tok");
      vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new Error("offline"));

      await act(async () => {
        await useUserStore.getState().initialize();
      });

      const state = useUserStore.getState();
      expect(state.user).toEqual({ username: "alice", token: "tok" });
      expect(state.isAuthenticated).toBe(true);
      expect(localStorage.getItem("novum_username")).toBe("alice");
    });
  });

  describe("register", () => {
    it("stores identity and authenticates on success", async () => {
      mockFetchOnce(201, { username: "bob", token: "bobtoken" });

      await act(async () => {
        await useUserStore.getState().register("bob");
      });

      const state = useUserStore.getState();
      expect(state.user).toEqual({ username: "bob", token: "bobtoken" });
      expect(state.isAuthenticated).toBe(true);
      expect(localStorage.getItem("novum_username")).toBe("bob");
      expect(localStorage.getItem("novum_token")).toBe("bobtoken");
    });

    it("throws with backend detail when registration fails", async () => {
      mockFetchOnce(409, { detail: "Username already exists" });

      await expect(
        useUserStore.getState().register("carol"),
      ).rejects.toThrow("Username already exists");

      const state = useUserStore.getState();
      expect(state.user).toBeNull();
      expect(state.isAuthenticated).toBe(false);
    });

    it("throws a generic error when backend body is empty", async () => {
      vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
        new Response("", { status: 500 }),
      );

      await expect(
        useUserStore.getState().register("dora"),
      ).rejects.toThrow("Registration failed");
    });
  });

  describe("logout", () => {
    it("clears identity and authentication state", () => {
      localStorage.setItem("novum_username", "alice");
      localStorage.setItem("novum_token", "tok");
      useUserStore.setState({
        user: { username: "alice", token: "tok" },
        isVerifying: false,
        isAuthenticated: true,
      });

      act(() => {
        useUserStore.getState().logout();
      });

      const state = useUserStore.getState();
      expect(state.user).toBeNull();
      expect(state.isAuthenticated).toBe(false);
      expect(localStorage.getItem("novum_username")).toBeNull();
      expect(localStorage.getItem("novum_token")).toBeNull();
    });
  });
});
