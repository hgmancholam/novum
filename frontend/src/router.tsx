/**
 * Route → Page mapping for Novum.
 * See ui-prototype.md §4 (Routes) and §8.3 (folder structure).
 *
 * Routes:
 * - `/` → HomePage (C1 + L + T1)
 * - `/runs/:runId` → RunPage (C4–C10 + L + T2/T3) — requires auth
 * - `/runs/:runId?fork=:eventId` → RunPage with fork context — requires auth
 * - `/diff/:runA/:runB` → DiffPage (C12 + L + T5) — requires auth
 *
 * ProtectedRoute: redirects unauthenticated users to `/`. While the token
 * is still being verified (isVerifying) it shows the loading skeleton so
 * the user is never flashed a redirect on a hard refresh with a valid token.
 */

import { createBrowserRouter, Navigate } from "react-router-dom";
import { lazy, Suspense, type ReactNode } from "react";

import { useUserStore } from "@/stores/userStore";

// Lazy load pages for code splitting
const HomePage = lazy(() => import("./pages/HomePage"));
const RunPage = lazy(() => import("./pages/RunPage"));
const DiffPage = lazy(() => import("./pages/DiffPage"));
const HowWeWorkPage = lazy(() => import("./pages/HowWeWorkPage"));

// Loading fallback component
function PageLoader() {
  return (
    <div className="flex h-screen items-center justify-center bg-(--bg-primary)">
      <div className="text-(--text-secondary)">Loading...</div>
    </div>
  );
}

// Wrap page in Suspense
function withSuspense(Component: React.ComponentType) {
  return (
    <Suspense fallback={<PageLoader />}>
      <Component />
    </Suspense>
  );
}

/**
 * Guards a route behind authentication.
 *
 * - isVerifying → show PageLoader (avoid flash-redirect on hard refresh).
 * - !isAuthenticated → redirect to `/`.
 * - isAuthenticated → render children.
 */
export function ProtectedRoute({ children }: { children: ReactNode }) {
  const isVerifying = useUserStore((s) => s.isVerifying);
  const isAuthenticated = useUserStore((s) => s.isAuthenticated);

  if (isVerifying) {
    return <PageLoader />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return children;
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: withSuspense(HomePage),
  },
  {
    path: "/how-we-work",
    element: withSuspense(HowWeWorkPage),
  },
  {
    path: "/runs/:runId",
    element: <ProtectedRoute>{withSuspense(RunPage)}</ProtectedRoute>,
  },
  {
    path: "/diff/:runA/:runB",
    element: <ProtectedRoute>{withSuspense(DiffPage)}</ProtectedRoute>,
  },
  {
    // Catch-all redirect to home
    path: "*",
    element: <Navigate to="/" replace />,
  },
]);
