/**
 * usePathname — reactive current pathname for components that live
 * OUTSIDE the `RouterProvider` tree (e.g. global modal containers
 * mounted as siblings in `main.tsx`).
 *
 * Subscribes to the `createBrowserRouter` instance directly so SPA
 * navigations (push / replace / back) trigger re-renders.
 */

import { useSyncExternalStore } from "react";
import { router } from "@/router";

function subscribe(onChange: () => void): () => void {
  return router.subscribe(onChange);
}

function getSnapshot(): string {
  return router.state.location.pathname;
}

function getServerSnapshot(): string {
  return "/";
}

export function usePathname(): string {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
