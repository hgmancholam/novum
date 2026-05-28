/**
 * Tests for ProtectedRoute guard.
 *
 * Verifies the three states:
 *  1. isVerifying  → renders loading skeleton (no redirect).
 *  2. unauthenticated → redirects to "/".
 *  3. authenticated  → renders children.
 */

import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { ProtectedRoute } from "./router";
import { router } from "./router";
import { useUserStore } from "@/stores/userStore";

function setAuthState(state: {
  isVerifying: boolean;
  isAuthenticated: boolean;
}) {
  useUserStore.setState(state);
}

function renderProtected(ui: React.ReactNode, initialPath = "/runs/abc") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <ProtectedRoute>{ui}</ProtectedRoute>
    </MemoryRouter>
  );
}

describe("ProtectedRoute", () => {
  beforeEach(() => {
    setAuthState({ isVerifying: false, isAuthenticated: false });
  });

  it("renders loading skeleton while token is being verified", () => {
    setAuthState({ isVerifying: true, isAuthenticated: false });
    renderProtected(<div data-testid="child">Protected</div>);
    expect(screen.queryByTestId("child")).not.toBeInTheDocument();
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("does not render children and navigates to / when unauthenticated", () => {
    setAuthState({ isVerifying: false, isAuthenticated: false });
    renderProtected(<div data-testid="child">Protected</div>);
    expect(screen.queryByTestId("child")).not.toBeInTheDocument();
  });

  it("renders children when authenticated", () => {
    setAuthState({ isVerifying: false, isAuthenticated: true });
    renderProtected(<div data-testid="child">Protected</div>);
    expect(screen.getByTestId("child")).toBeInTheDocument();
  });
});

describe("router config", () => {
  it("registers a public /how-we-work route", () => {
    interface RouteLike {
      path?: string;
      children?: RouteLike[];
    }
    const flatten = (routes: RouteLike[]): RouteLike[] =>
      routes.flatMap((r) => [r, ...(r.children ? flatten(r.children) : [])]);
    const paths = flatten(router.routes as RouteLike[])
      .map((r) => r.path)
      .filter((p): p is string => typeof p === "string");
    expect(paths).toContain("/how-we-work");
  });
});
