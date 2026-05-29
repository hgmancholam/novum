/**
 * Route → Page mapping for Novum.
 * See ui-prototype.md §4 (Routes) and §8.3 (folder structure).
 *
 * Routes:
 * - `/` → HowWeWorkPage (public marketing / storytelling)
 * - `/run` → HomePage (C1 + L + T1) — entry point to start a research
 * - `/runs/:runId` → RunPage (C4–C10 + L + T2/T3) — requires auth
 * - `/runs/:runId?fork=:eventId` → RunPage with fork context — requires auth
 * - `/diff/:runA/:runB` → DiffPage (C12 + L + T5) — requires auth
 *
 * ProtectedRoute: redirects unauthenticated users to `/run`. While the token
 * is still being verified (isVerifying) it shows the loading skeleton so
 * the user is never flashed a redirect on a hard refresh with a valid token.
 */

import { createBrowserRouter, Navigate, Outlet } from "react-router-dom";
import { lazy, Suspense, useMemo, useState, type ReactNode } from "react";
import { ServiceStatusBar } from "@/components/organisms";
import { ServiceHealthWarningModal } from "@/components/molecules";
import { useServiceHealth } from "@/hooks/useServiceHealth";

import { useUserStore } from "@/stores/userStore";

// Lazy load pages for code splitting
const HomePage = lazy(() => import("./pages/HomePage"));
const RunPage = lazy(() => import("./pages/RunPage"));
const DiffPage = lazy(() => import("./pages/DiffPage"));
const HowWeWorkPage = lazy(() => import("./pages/HowWeWorkPage"));
const CostAnalyticsPage = lazy(() => import("./pages/CostAnalyticsPage"));

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
 * Layout for /run and /runs/:runId — renders the page outlet plus the
 * service-health footer bar and, on first load, a warning modal if any
 * non-disabled service is failing (BRD-27).
 */
function RunShell() {
  const { data } = useServiceHealth();
  const [dismissed, setDismissed] = useState(false);

  const problematic = useMemo(
    () =>
      (data?.services ?? []).filter(
        (s) => s.status !== "ok" && s.status !== "disabled",
      ),
    [data],
  );

  return (
    <>
      <Outlet />
      <div className="fixed bottom-0 left-0 right-0 z-40">
        <ServiceStatusBar />
      </div>
      {problematic.length > 0 && !dismissed && (
        <ServiceHealthWarningModal
          services={problematic}
          onClose={() => { setDismissed(true); }}
        />
      )}
    </>
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
    return <Navigate to="/run" replace />;
  }

  return children;
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: withSuspense(HowWeWorkPage),
  },
  {
    element: <RunShell />,
    children: [
      {
        path: "/run",
        element: withSuspense(HomePage),
      },
      {
        path: "/runs/:runId",
        element: <ProtectedRoute>{withSuspense(RunPage)}</ProtectedRoute>,
      },
    ],
  },
  {
    path: "/diff/:runA/:runB",
    element: <ProtectedRoute>{withSuspense(DiffPage)}</ProtectedRoute>,
  },
  {
    path: "/costs",
    element: <ProtectedRoute>{withSuspense(CostAnalyticsPage)}</ProtectedRoute>,
  },
  {
    // Catch-all redirect to home
    path: "*",
    element: <Navigate to="/" replace />,
  },
]);
