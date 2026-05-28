import { describe, it, expect, beforeEach } from "vitest";
import { act, render, screen, fireEvent } from "@testing-library/react";
import { axe } from "jest-axe";
import { AppShell } from "./AppShell";
import { useSelectionStore } from "@/stores/selectionStore";
import { useUserStore } from "@/stores/userStore";
import { useLoginModal } from "@/hooks/useLoginModal";

function resetStore(): void {
  useSelectionStore.setState({
    selectedRunId: null,
    selectedEventId: null,
    leftPanelOpen: false,
    rightPanelOpen: false,
    isTracePanelCollapsed: false,
  });
  useUserStore.setState({
    user: null,
    isVerifying: false,
    isAuthenticated: false,
  });
  useLoginModal.setState({ isOpen: false });
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
    // TopBar renders on every breakpoint (iter 2) — hamburger/PanelRight
    // toggles are hidden on desktop.
    expect(screen.getByTestId("top-bar")).toBeInTheDocument();
    expect(screen.queryByLabelText("Open history")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Open trace")).not.toBeInTheDocument();
  });

  it("hides left panel and shows top bar on tablet", () => {
    render(<AppShell forceBreakpoint="tablet" {...slots} />);
    expect(screen.queryByTestId("app-shell-left")).not.toBeInTheDocument();
    expect(screen.getByTestId("app-shell-right")).toBeInTheDocument();
    expect(screen.getByTestId("top-bar")).toBeInTheDocument();
    expect(screen.getByLabelText("Open history")).toBeInTheDocument();
    // Right panel is inline on tablet, so PanelRight toggle is hidden.
    expect(screen.queryByLabelText("Open trace")).not.toBeInTheDocument();
  });

  it("hides both side panels on mobile", () => {
    render(<AppShell forceBreakpoint="mobile" {...slots} />);
    expect(screen.queryByTestId("app-shell-left")).not.toBeInTheDocument();
    expect(screen.queryByTestId("app-shell-right")).not.toBeInTheDocument();
    expect(screen.getByTestId("top-bar")).toBeInTheDocument();
    expect(screen.getByLabelText("Open history")).toBeInTheDocument();
    expect(screen.getByLabelText("Open trace")).toBeInTheDocument();
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

  it("renders the 'How do we work?' link in the top bar", () => {
    render(<AppShell forceBreakpoint="desktop" {...slots} />);
    const link = screen.getByRole("link", { name: /how do we work\?/i });
    expect(link).toHaveAttribute("href", "/");
  });

  it("keeps the 'How do we work?' link reachable on mobile too", () => {
    render(<AppShell forceBreakpoint="mobile" {...slots} />);
    expect(
      screen.getByRole("link", { name: /how do we work\?/i })
    ).toBeInTheDocument();
  });

  it("has no a11y violations on desktop", async () => {
    const { container } = render(
      <AppShell forceBreakpoint="desktop" {...slots} />
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  describe("IdentitySlot wiring (iter 2)", () => {
    it("shows the Spinner while isVerifying on desktop", () => {
      useUserStore.setState({
        user: null,
        isVerifying: true,
        isAuthenticated: false,
      });
      render(<AppShell forceBreakpoint="desktop" {...slots} />);
      const slot = screen.getByTestId("identity-slot");
      expect(slot).toHaveAttribute("data-state", "verifying");
      expect(slot.querySelector('[role="status"]')).not.toBeNull();
    });

    it("shows Sign in when unauthenticated and not verifying", () => {
      render(<AppShell forceBreakpoint="desktop" {...slots} />);
      expect(
        screen.getByRole("button", { name: "Sign in" })
      ).toBeInTheDocument();
    });

    it("opens the login modal signal when Sign in is clicked", () => {
      render(<AppShell forceBreakpoint="desktop" {...slots} />);
      fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
      expect(useLoginModal.getState().isOpen).toBe(true);
    });

    it("shows username pill and Logout when authenticated", () => {
      useUserStore.setState({
        user: { username: "alice", token: "tok" },
        isVerifying: false,
        isAuthenticated: true,
      });
      render(<AppShell forceBreakpoint="desktop" {...slots} />);
      expect(screen.getByText("alice")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Logout" })
      ).toBeInTheDocument();
    });

    it("clears the store when Logout is clicked", () => {
      useUserStore.setState({
        user: { username: "alice", token: "tok" },
        isVerifying: false,
        isAuthenticated: true,
      });
      render(<AppShell forceBreakpoint="desktop" {...slots} />);
      fireEvent.click(screen.getByRole("button", { name: "Logout" }));
      expect(useUserStore.getState().isAuthenticated).toBe(false);
      expect(useUserStore.getState().user).toBeNull();
    });

    it("renders the IdentitySlot on tablet and mobile too", () => {
      const { rerender } = render(
        <AppShell forceBreakpoint="tablet" {...slots} />
      );
      expect(screen.getByTestId("identity-slot")).toBeInTheDocument();
      rerender(<AppShell forceBreakpoint="mobile" {...slots} />);
      expect(screen.getByTestId("identity-slot")).toBeInTheDocument();
    });
  });
});
