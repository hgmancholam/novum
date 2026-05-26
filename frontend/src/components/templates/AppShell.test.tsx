import { describe, it, expect, beforeEach } from "vitest";
import { act, render, screen, fireEvent } from "@testing-library/react";
import { axe } from "jest-axe";
import { AppShell } from "./AppShell";
import { useSelectionStore } from "@/stores/selectionStore";

function resetStore(): void {
  useSelectionStore.setState({
    selectedRunId: null,
    selectedEventId: null,
    leftPanelOpen: false,
    rightPanelOpen: false,
  });
}

const slots = {
  left: <div data-testid="slot-left">LEFT</div>,
  center: <div data-testid="slot-center">CENTER</div>,
  right: <div data-testid="slot-right">RIGHT</div>,
};

describe("AppShell", () => {
  beforeEach(() => {
    resetStore();
  });

  it("renders all three slots on desktop", () => {
    render(<AppShell forceBreakpoint="desktop" {...slots} />);
    expect(screen.getByTestId("slot-left")).toBeInTheDocument();
    expect(screen.getByTestId("slot-center")).toBeInTheDocument();
    expect(screen.getByTestId("slot-right")).toBeInTheDocument();
    expect(screen.getByTestId("app-shell-left")).toBeInTheDocument();
    expect(screen.getByTestId("app-shell-right")).toBeInTheDocument();
    expect(screen.queryByTestId("mobile-top-bar")).not.toBeInTheDocument();
  });

  it("hides left panel and shows mobile top bar on tablet", () => {
    render(<AppShell forceBreakpoint="tablet" {...slots} />);
    expect(screen.queryByTestId("app-shell-left")).not.toBeInTheDocument();
    expect(screen.getByTestId("app-shell-right")).toBeInTheDocument();
    expect(screen.getByTestId("mobile-top-bar")).toBeInTheDocument();
  });

  it("hides both side panels on mobile", () => {
    render(<AppShell forceBreakpoint="mobile" {...slots} />);
    expect(screen.queryByTestId("app-shell-left")).not.toBeInTheDocument();
    expect(screen.queryByTestId("app-shell-right")).not.toBeInTheDocument();
    expect(screen.getByTestId("mobile-top-bar")).toBeInTheDocument();
  });

  it("opens the left drawer when store flag is true (tablet)", () => {
    render(<AppShell forceBreakpoint="tablet" {...slots} />);
    expect(screen.queryByTestId("drawer-left")).not.toBeInTheDocument();
    act(() => {
      useSelectionStore.getState().openLeftPanel();
    });
    expect(screen.getByTestId("drawer-left")).toBeInTheDocument();
  });

  it("opens the right drawer on mobile", () => {
    render(<AppShell forceBreakpoint="mobile" {...slots} />);
    act(() => {
      useSelectionStore.getState().openRightPanel();
    });
    expect(screen.getByTestId("drawer-right")).toBeInTheDocument();
  });

  it("closes drawer when overlay is clicked", () => {
    render(<AppShell forceBreakpoint="mobile" {...slots} />);
    act(() => {
      useSelectionStore.getState().openLeftPanel();
    });
    fireEvent.click(screen.getByTestId("drawer-overlay-left"));
    expect(useSelectionStore.getState().leftPanelOpen).toBe(false);
  });

  it("closes drawer when Escape is pressed", () => {
    render(<AppShell forceBreakpoint="mobile" {...slots} />);
    act(() => {
      useSelectionStore.getState().openLeftPanel();
    });
    fireEvent.keyDown(window, { key: "Escape" });
    expect(useSelectionStore.getState().leftPanelOpen).toBe(false);
  });

  it("top-bar button opens the left drawer", () => {
    render(<AppShell forceBreakpoint="mobile" {...slots} />);
    fireEvent.click(screen.getByLabelText("Open history"));
    expect(useSelectionStore.getState().leftPanelOpen).toBe(true);
  });

  it("top-bar button opens the right drawer", () => {
    render(<AppShell forceBreakpoint="mobile" {...slots} />);
    fireEvent.click(screen.getByLabelText("Open trace"));
    expect(useSelectionStore.getState().rightPanelOpen).toBe(true);
  });

  it("exposes the breakpoint via data-attribute", () => {
    render(<AppShell forceBreakpoint="desktop" {...slots} />);
    expect(screen.getByTestId("app-shell")).toHaveAttribute(
      "data-breakpoint",
      "desktop"
    );
  });

  it("has no a11y violations on desktop", async () => {
    const { container } = render(
      <AppShell forceBreakpoint="desktop" {...slots} />
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
