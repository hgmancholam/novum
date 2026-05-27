import {
  describe,
  it,
  expect,
  beforeEach,
  afterEach,
  vi,
} from "vitest";
import { render, screen, act } from "@testing-library/react";

import { Toaster } from "./Toaster";
import { useToastStore } from "@/stores/toastStore";

beforeEach(() => {
  useToastStore.getState().reset();
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("Toaster", () => {
  it("renders nothing when there are no toasts", () => {
    render(<Toaster />);
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("renders an error toast with role='alert' and the literal microcopy", () => {
    render(<Toaster />);
    act(() => {
      useToastStore.getState().push({
        kind: "error",
        message: "Couldn't delete the run. Please try again.",
      });
    });
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(
      "Couldn't delete the run. Please try again."
    );
  });

  it("auto-dismisses after 5 seconds (single advanceTimersByTime call per L-009)", () => {
    render(<Toaster />);
    act(() => {
      useToastStore.getState().push({ kind: "error", message: "boom" });
    });
    expect(screen.getByRole("alert")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(useToastStore.getState().toasts).toHaveLength(0);
  });

  it("stacks multiple toasts", () => {
    render(<Toaster />);
    act(() => {
      useToastStore.getState().push({ kind: "error", message: "first" });
      useToastStore.getState().push({ kind: "info", message: "second" });
    });
    expect(screen.getByText("first")).toBeInTheDocument();
    expect(screen.getByText("second")).toBeInTheDocument();
  });
});
