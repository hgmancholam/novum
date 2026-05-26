import { describe, it, expect, beforeEach } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useLoginModal } from "./useLoginModal";

describe("useLoginModal", () => {
  beforeEach(() => {
    useLoginModal.setState({ isOpen: false });
  });

  it("starts closed", () => {
    const { result } = renderHook(() => useLoginModal());
    expect(result.current.isOpen).toBe(false);
  });

  it("opens via open()", () => {
    const { result } = renderHook(() => useLoginModal());
    act(() => {
      result.current.open();
    });
    expect(result.current.isOpen).toBe(true);
  });

  it("closes via close()", () => {
    useLoginModal.setState({ isOpen: true });
    const { result } = renderHook(() => useLoginModal());
    act(() => {
      result.current.close();
    });
    expect(result.current.isOpen).toBe(false);
  });

  it("shares state across two consumers", () => {
    const a = renderHook(() => useLoginModal());
    const b = renderHook(() => useLoginModal());
    expect(a.result.current.isOpen).toBe(false);
    expect(b.result.current.isOpen).toBe(false);
    act(() => {
      a.result.current.open();
    });
    expect(a.result.current.isOpen).toBe(true);
    expect(b.result.current.isOpen).toBe(true);
    act(() => {
      b.result.current.close();
    });
    expect(a.result.current.isOpen).toBe(false);
    expect(b.result.current.isOpen).toBe(false);
  });
});
