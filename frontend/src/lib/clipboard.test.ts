/**
 * Unit tests for clipboard utilities.
 * BRD-00 validation: Verify clipboard helpers per ui-prototype.md §8.3.
 *
 * Per workflow.md F3.S3: generate_unit_tests
 */

import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { copyToClipboard, copyRunUrl, copyDiffUrl } from "./clipboard";

describe("copyToClipboard", () => {
  const originalClipboard = navigator.clipboard;
  const originalExecCommand = document.execCommand;

  beforeEach(() => {
    // Reset mocks
    vi.restoreAllMocks();
  });

  afterEach(() => {
    // Restore originals
    Object.defineProperty(navigator, "clipboard", {
      value: originalClipboard,
      writable: true,
    });
    document.execCommand = originalExecCommand;
  });

  it("uses Clipboard API when available", async () => {
    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: writeTextMock },
      writable: true,
    });

    await copyToClipboard("test text");

    expect(writeTextMock).toHaveBeenCalledWith("test text");
  });

  it("falls back to execCommand when Clipboard API unavailable", async () => {
    Object.defineProperty(navigator, "clipboard", {
      value: undefined,
      writable: true,
    });

    const execCommandMock = vi.fn().mockReturnValue(true);
    document.execCommand = execCommandMock;

    await copyToClipboard("test text");

    expect(execCommandMock).toHaveBeenCalledWith("copy");
  });
});

describe("copyRunUrl", () => {
  beforeEach(() => {
    // Mock window.location.origin
    Object.defineProperty(window, "location", {
      value: { origin: "https://novum.example.com" },
      writable: true,
    });

    // Mock clipboard
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      writable: true,
    });
  });

  it("copies correct run URL format", async () => {
    await copyRunUrl("abc123");

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      "https://novum.example.com/runs/abc123"
    );
  });
});

describe("copyDiffUrl", () => {
  beforeEach(() => {
    Object.defineProperty(window, "location", {
      value: { origin: "https://novum.example.com" },
      writable: true,
    });

    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      writable: true,
    });
  });

  it("copies correct diff URL format", async () => {
    await copyDiffUrl("run1", "run2");

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      "https://novum.example.com/diff/run1/run2"
    );
  });
});
