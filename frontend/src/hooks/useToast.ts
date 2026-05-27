/**
 * useToast — thin hook exposing the toast push/dismiss API.
 *
 * Components should call ``useToast().push({ kind, message })`` rather
 * than touching the Zustand store directly so we have one seam to swap
 * the implementation later (e.g. shadcn/sonner).
 */

import { useToastStore, type ToastInput } from "@/stores/toastStore";

export interface ToastApi {
  push: (toast: ToastInput) => number;
  dismiss: (id: number) => void;
}

export function useToast(): ToastApi {
  const push = useToastStore((s) => s.push);
  const dismiss = useToastStore((s) => s.dismiss);
  return { push, dismiss };
}
