/**
 * Shared QueryClient instance.
 *
 * Extracted from main.tsx so that userStore.logout() can call
 * queryClient.clear() without creating a circular dependency.
 */

import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60,
      retry: 1,
    },
  },
});
