/**
 * Toast store (BRD-20 §14.3, RF-13).
 *
 * Minimal stack: at most ~3 active toasts; the Toaster molecule renders
 * them, auto-dismissing each after 5s. Push returns the assigned id so
 * callers can dismiss imperatively (rare).
 */

import { create } from "zustand";

export type ToastKind = "error" | "info" | "success";

export interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}

export interface ToastInput {
  kind: ToastKind;
  message: string;
}

interface ToastStoreState {
  toasts: Toast[];
  push: (toast: ToastInput) => number;
  dismiss: (id: number) => void;
  reset: () => void;
}

let nextId = 1;

export const useToastStore = create<ToastStoreState>((set) => ({
  toasts: [],
  push: (toast) => {
    const id = nextId++;
    set((state) => ({ toasts: [...state.toasts, { id, ...toast }] }));
    return id;
  },
  dismiss: (id) => {
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
  },
  reset: () => {
    set({ toasts: [] });
  },
}));
