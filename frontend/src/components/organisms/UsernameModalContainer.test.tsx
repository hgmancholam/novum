import { describe, it, expect, beforeEach, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { axe } from "jest-axe";

// Mock pathname so tests can simulate routes without mounting RouterProvider.
let mockPathname = "/run";
vi.mock("@/hooks/usePathname", () => ({
  usePathname: () => mockPathname,
}));

import { UsernameModalContainer } from "./UsernameModalContainer";
import { useUserStore } from "@/stores/userStore";
import { useLoginModal } from "@/hooks/useLoginModal";

function resetStores(): void {
  useUserStore.setState({
    user: null,
    isVerifying: true,
    isAuthenticated: false,
  });
  useLoginModal.setState({ isOpen: false });
}

describe("UsernameModalContainer", () => {
  beforeEach(() => {
    resetStores();
    mockPathname = "/run";
  });

  it("is hidden while isVerifying", () => {
    useUserStore.setState({
      user: null,
      isVerifying: true,
      isAuthenticated: false,
    });
    render(<UsernameModalContainer />);
    expect(screen.queryByTestId("username-modal")).not.toBeInTheDocument();
  });

  it("is shown after initialize resolves with no stored identity", () => {
    useUserStore.setState({
      user: null,
      isVerifying: false,
      isAuthenticated: false,
    });
    render(<UsernameModalContainer />);
    expect(screen.getByTestId("username-modal")).toBeInTheDocument();
  });

  it("is hidden after a successful register (authenticated)", () => {
    useUserStore.setState({
      user: { username: "bob", token: "tok" },
      isVerifying: false,
      isAuthenticated: true,
    });
    render(<UsernameModalContainer />);
    expect(screen.queryByTestId("username-modal")).not.toBeInTheDocument();
  });

  it("is shown again after logout (transition to unauthenticated)", () => {
    useUserStore.setState({
      user: { username: "bob", token: "tok" },
      isVerifying: false,
      isAuthenticated: true,
    });
    render(<UsernameModalContainer />);
    expect(screen.queryByTestId("username-modal")).not.toBeInTheDocument();
    act(() => {
      useUserStore.setState({
        user: null,
        isVerifying: false,
        isAuthenticated: false,
      });
    });
    expect(screen.getByTestId("username-modal")).toBeInTheDocument();
  });

  it("opens when useLoginModal.open() is called even while authenticated", () => {
    useUserStore.setState({
      user: { username: "bob", token: "tok" },
      isVerifying: false,
      isAuthenticated: true,
    });
    render(<UsernameModalContainer />);
    expect(screen.queryByTestId("username-modal")).not.toBeInTheDocument();
    act(() => {
      useLoginModal.getState().open();
    });
    expect(screen.getByTestId("username-modal")).toBeInTheDocument();
  });

  it("has no a11y violations when visible", async () => {
    useUserStore.setState({
      user: null,
      isVerifying: false,
      isAuthenticated: false,
    });
    const { container } = render(<UsernameModalContainer />);
    expect(await axe(container)).toHaveNoViolations();
  });

  it("does NOT auto-open on the public route '/' when unauthenticated", () => {
    mockPathname = "/";
    useUserStore.setState({
      user: null,
      isVerifying: false,
      isAuthenticated: false,
    });
    render(<UsernameModalContainer />);
    expect(screen.queryByTestId("username-modal")).not.toBeInTheDocument();
  });

  it("still opens on '/' when useLoginModal.open() is called manually", () => {
    mockPathname = "/";
    useUserStore.setState({
      user: null,
      isVerifying: false,
      isAuthenticated: false,
    });
    render(<UsernameModalContainer />);
    expect(screen.queryByTestId("username-modal")).not.toBeInTheDocument();
    act(() => {
      useLoginModal.getState().open();
    });
    expect(screen.getByTestId("username-modal")).toBeInTheDocument();
  });
});
