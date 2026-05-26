/**
 * Unit tests for lib/auth.ts (BRD-04 §4.7).
 */

import { beforeEach, describe, expect, it } from "vitest";

import {
  clearIdentity,
  getAuthHeaders,
  getStoredIdentity,
  storeIdentity,
} from "./auth";

describe("lib/auth", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe("getStoredIdentity", () => {
    it("returns null when no identity is stored", () => {
      expect(getStoredIdentity()).toBeNull();
    });

    it("returns null when only username is stored", () => {
      localStorage.setItem("novum_username", "alice");
      expect(getStoredIdentity()).toBeNull();
    });

    it("returns null when only token is stored", () => {
      localStorage.setItem("novum_token", "abc");
      expect(getStoredIdentity()).toBeNull();
    });

    it("returns the identity when both keys are present", () => {
      localStorage.setItem("novum_username", "alice");
      localStorage.setItem("novum_token", "abc");
      expect(getStoredIdentity()).toEqual({ username: "alice", token: "abc" });
    });
  });

  describe("storeIdentity", () => {
    it("persists username and token to localStorage", () => {
      storeIdentity({ username: "bob", token: "xyz" });
      expect(localStorage.getItem("novum_username")).toBe("bob");
      expect(localStorage.getItem("novum_token")).toBe("xyz");
    });

    it("round-trips through getStoredIdentity", () => {
      storeIdentity({ username: "carol", token: "ttt" });
      expect(getStoredIdentity()).toEqual({ username: "carol", token: "ttt" });
    });
  });

  describe("clearIdentity", () => {
    it("removes both keys from localStorage", () => {
      storeIdentity({ username: "dora", token: "ddd" });
      clearIdentity();
      expect(localStorage.getItem("novum_username")).toBeNull();
      expect(localStorage.getItem("novum_token")).toBeNull();
      expect(getStoredIdentity()).toBeNull();
    });

    it("is safe to call when nothing is stored", () => {
      expect(() => {
        clearIdentity();
      }).not.toThrow();
    });
  });

  describe("getAuthHeaders", () => {
    it("returns an empty object when no identity is stored", () => {
      expect(getAuthHeaders()).toEqual({});
    });

    it("returns X-Username and X-Token when identity is stored", () => {
      storeIdentity({ username: "eve", token: "tkn" });
      expect(getAuthHeaders()).toEqual({
        "X-Username": "eve",
        "X-Token": "tkn",
      });
    });
  });
});
