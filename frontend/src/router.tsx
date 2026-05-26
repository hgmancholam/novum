/**
 * Route → Page mapping for Novum.
 * See ui-prototype.md §4 (Routes) and §8.3 (folder structure).
 *
 * Routes:
 * - `/` → HomePage (C1 + L + T1)
 * - `/runs/:runId` → RunPage (C4–C10 + L + T2/T3)
 * - `/runs/:runId?fork=:eventId` → RunPage with fork context
 * - `/diff/:runA/:runB` → DiffPage (C12 + L + T5)
 */

import { createBrowserRouter, Navigate } from "react-router-dom";
import { lazy, Suspense } from "react";

// Lazy load pages for code splitting
const HomePage = lazy(() => import("./pages/HomePage"));
const RunPage = lazy(() => import("./pages/RunPage"));
const DiffPage = lazy(() => import("./pages/DiffPage"));

// Loading fallback component
function PageLoader() {
  return (
    <div className="flex h-screen items-center justify-center bg-[var(--bg-primary)]">
      <div className="text-[var(--text-secondary)]">Loading...</div>
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

export const router = createBrowserRouter([
  {
    path: "/",
    element: withSuspense(HomePage),
  },
  {
    path: "/runs/:runId",
    element: withSuspense(RunPage),
  },
  {
    path: "/diff/:runA/:runB",
    element: withSuspense(DiffPage),
  },
  {
    // Catch-all redirect to home
    path: "*",
    element: <Navigate to="/" replace />,
  },
]);
