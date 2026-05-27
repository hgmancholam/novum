/**
 * Toaster molecule (BRD-20 §14.3, RF-13).
 *
 * Fixed top-right stack of transient notifications. Each toast slides
 * in over 180ms, auto-dismisses after 5s, and respects
 * `prefers-reduced-motion` via Motion's `useReducedMotion` (animations
 * collapse to instant).
 */

import { useEffect } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";

import { useToastStore, type Toast } from "@/stores/toastStore";
import { cn } from "@/lib/cn";

const AUTO_DISMISS_MS = 5000;

interface ToastRowProps {
  toast: Toast;
  reducedMotion: boolean;
  onDismiss: (id: number) => void;
}

function ToastRow({ toast, reducedMotion, onDismiss }: ToastRowProps) {
  useEffect(() => {
    const handle = window.setTimeout(() => {
      onDismiss(toast.id);
    }, AUTO_DISMISS_MS);
    return () => {
      window.clearTimeout(handle);
    };
  }, [toast.id, onDismiss]);

  const duration = reducedMotion ? 0 : 0.18;
  const offset = reducedMotion ? 0 : 16;

  return (
    <motion.li
      layout
      initial={{ opacity: 0, x: offset }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: offset }}
      transition={{ duration }}
      role={toast.kind === "error" ? "alert" : "status"}
      className={cn(
        "pointer-events-auto min-w-[16rem] max-w-sm rounded-md border px-4 py-2 text-sm shadow-md",
        toast.kind === "error" &&
          "border-red-300 bg-red-50 text-red-900 dark:border-red-800 dark:bg-red-950/80 dark:text-red-100",
        toast.kind === "info" &&
          "border-slate-300 bg-white text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100",
        toast.kind === "success" &&
          "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-100"
      )}
    >
      {toast.message}
    </motion.li>
  );
}

export function Toaster() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);
  const reducedMotion = useReducedMotion() ?? false;

  return (
    <ul
      aria-live="polite"
      className="pointer-events-none fixed right-4 top-4 z-50 flex w-auto flex-col gap-2"
    >
      <AnimatePresence initial={false}>
        {toasts.map((toast) => (
          <ToastRow
            key={toast.id}
            toast={toast}
            reducedMotion={reducedMotion}
            onDismiss={dismiss}
          />
        ))}
      </AnimatePresence>
    </ul>
  );
}
