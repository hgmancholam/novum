import { StrictMode, useEffect, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";
import { router } from "./router";
import { UsernameModalContainer } from "@/components/organisms";
import { useUserStore } from "@/stores/userStore";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60,
      retry: 1,
    },
  },
});

// Module-level guard: ensures `initialize()` runs exactly once even when
// React 19 StrictMode double-invokes effects in dev. See IP-11 iter 2 §4.1.
let initStarted = false;

export function __resetAppBootForTests(): void {
  initStarted = false;
}

export interface AppBootProps {
  children: ReactNode;
}

export function AppBoot({ children }: AppBootProps) {
  useEffect(() => {
    if (initStarted) return;
    initStarted = true;
    void useUserStore.getState().initialize();
  }, []);

  return (
    <>
      {children}
      <UsernameModalContainer />
    </>
  );
}

const rootElement = document.getElementById("root");
if (rootElement) {
  createRoot(rootElement).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <AppBoot>
          <RouterProvider router={router} />
        </AppBoot>
      </QueryClientProvider>
    </StrictMode>
  );
}
