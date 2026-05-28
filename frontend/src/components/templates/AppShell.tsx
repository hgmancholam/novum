/**
 * AppShell template — the root 3-panel layout.
 * See ui-prototype.md §2 (layout), §8.2 (templates), §9.16 (responsive strategy),
 * and BRD-11 AC-01..AC-03.
 *
 * Breakpoints:
 *   desktop (>=1024px): left=260px, right=360px, center fluid. All visible.
 *   tablet  (768-1023): left collapses to drawer. right=320px stays. center fluid.
 *   mobile  (<768px):   only center visible. left/right open as full-height drawers.
 *
 * Drawer state is owned by useSelectionStore (cross-component).
 * Animations follow §1.6 (200ms easeOut).
 */

import { useEffect, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Menu, PanelRight, Workflow } from "lucide-react";
import { cn } from "@/lib/cn";
import { Logo } from "@/components/atoms";
import { IdentitySlot } from "@/components/molecules";
import { useSelectionStore } from "@/stores/selectionStore";

export type Breakpoint = "mobile" | "tablet" | "desktop";

export interface AppShellProps {
  left: ReactNode;
  center: ReactNode;
  right: ReactNode;
  /**
   * Optional breakpoint override for tests / Storybook.
   * When omitted, AppShell reads matchMedia at mount and on resize.
   */
  forceBreakpoint?: Breakpoint;
}

function readBreakpoint(): Breakpoint {
  if (typeof window === "undefined") return "desktop";
  if (window.matchMedia("(min-width: 1024px)").matches) return "desktop";
  if (window.matchMedia("(min-width: 768px)").matches) return "tablet";
  return "mobile";
}

function useBreakpoint(forced?: Breakpoint): Breakpoint {
  const [bp, setBp] = useState<Breakpoint>(() => forced ?? readBreakpoint());

  useEffect(() => {
    if (forced !== undefined) {
      setBp(forced);
      return;
    }
    const update = (): void => {
      setBp(readBreakpoint());
    };
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("resize", update);
    };
  }, [forced]);

  return bp;
}

const drawerTransition = { duration: 0.2, ease: "easeOut" as const };

interface DrawerProps {
  side: "left" | "right";
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  labelledBy: string;
}

function Drawer({ side, open, onClose, children, labelledBy }: DrawerProps) {
  // Keyboard: Esc closes.
  useEffect(() => {
    if (!open) return;
    const handle = (e: KeyboardEvent): void => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handle);
    return () => {
      window.removeEventListener("keydown", handle);
    };
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open ? (
        <>
          <motion.div
            data-testid={`drawer-overlay-${side}`}
            className="fixed inset-0 z-40 bg-black/60"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={drawerTransition}
            onClick={onClose}
            aria-hidden="true"
          />
          <motion.aside
            role="dialog"
            aria-modal="true"
            aria-labelledby={labelledBy}
            data-testid={`drawer-${side}`}
            className={cn(
              "fixed inset-y-0 z-50 flex w-[88vw] max-w-[360px] flex-col " +
                "bg-[var(--bg-secondary)] shadow-[0_8px_32px_rgba(0,0,0,0.4)]",
              side === "left" ? "left-0" : "right-0"
            )}
            initial={{ x: side === "left" ? "-100%" : "100%" }}
            animate={{ x: 0 }}
            exit={{ x: side === "left" ? "-100%" : "100%" }}
            transition={drawerTransition}
          >
            {children}
          </motion.aside>
        </>
      ) : null}
    </AnimatePresence>
  );
}

interface TopBarProps {
  showLeftToggle: boolean;
  showRightToggle: boolean;
  onOpenLeft: () => void;
  onOpenRight: () => void;
}

function TopBar({
  showLeftToggle,
  showRightToggle,
  onOpenLeft,
  onOpenRight,
}: TopBarProps) {
  return (
    <div
      data-testid="top-bar"
      className="flex h-12 items-center justify-between border-b border-[var(--glass-border)] bg-[var(--bg-secondary)] px-3"
    >
      <div className="flex items-center gap-2">
        {showLeftToggle ? (
          <button
            type="button"
            onClick={onOpenLeft}
            aria-label="Open history"
            className="inline-flex h-9 w-9 items-center justify-center rounded-md text-[var(--text-primary)] hover:bg-[var(--glass-bg)]"
          >
            <Menu className="h-5 w-5" strokeWidth={1.5} aria-hidden="true" />
          </button>
        ) : null}
        <span
          id="appshell-title"
          className="inline-flex items-center gap-2 text-base font-medium text-[var(--text-primary)]"
        >
          <Logo size={20} title="" />
          Novum
        </span>
      </div>
      <div className="flex items-center gap-2">
        <a
          href="/"
          aria-label="How do we work?"
          className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs text-(--text-secondary) transition-colors hover:bg-(--glass-bg) hover:text-(--text-primary)"
        >
          <Workflow className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden="true" />
          <span className="hidden sm:inline">How do we work?</span>
        </a>
        <IdentitySlot />
        {showRightToggle ? (
          <button
            type="button"
            onClick={onOpenRight}
            aria-label="Open trace"
            className="inline-flex h-9 w-9 items-center justify-center rounded-md text-[var(--text-primary)] hover:bg-[var(--glass-bg)]"
          >
            <PanelRight className="h-5 w-5" strokeWidth={1.5} aria-hidden="true" />
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function AppShell({ left, center, right, forceBreakpoint }: AppShellProps) {
  const breakpoint = useBreakpoint(forceBreakpoint);
  const leftPanelOpen = useSelectionStore((s) => s.leftPanelOpen);
  const rightPanelOpen = useSelectionStore((s) => s.rightPanelOpen);
  const openLeftPanel = useSelectionStore((s) => s.openLeftPanel);
  const openRightPanel = useSelectionStore((s) => s.openRightPanel);
  const closePanels = useSelectionStore((s) => s.closePanels);
  // IP-24 Phase 5: Trace panel collapse state
  const isTracePanelCollapsed = useSelectionStore((s) => s.isTracePanelCollapsed);

  const showLeftAsDrawer = breakpoint !== "desktop";
  const showRightAsDrawer = breakpoint === "mobile";

  return (
    <div
      data-testid="app-shell"
      data-breakpoint={breakpoint}
      className="flex h-[100dvh] w-full overflow-hidden bg-transparent text-[var(--text-primary)]"
    >
      {showLeftAsDrawer ? null : (
        <aside
          data-testid="app-shell-left"
          aria-label="History"
          className="h-full w-[260px] flex-shrink-0 border-r border-[var(--glass-border)]"
        >
          {left}
        </aside>
      )}

      <main
        data-testid="app-shell-main"
        className="flex h-full min-w-0 flex-1 flex-col"
      >
        <TopBar
          showLeftToggle={showLeftAsDrawer}
          showRightToggle={showRightAsDrawer}
          onOpenLeft={openLeftPanel}
          onOpenRight={openRightPanel}
        />
        <div className="flex-1 overflow-hidden">{center}</div>
      </main>

      {showRightAsDrawer ? null : (
        <aside
          data-testid="app-shell-right"
          aria-label="Trace"
          className={cn(
            "h-full flex-shrink-0 border-l border-[var(--glass-border)]",
            // IP-24 Phase 5: Narrow width when collapsed
            isTracePanelCollapsed
              ? "w-10"
              : breakpoint === "tablet"
                ? "w-[320px]"
                : "w-[360px]"
          )}
        >
          {right}
        </aside>
      )}

      {showLeftAsDrawer ? (
        <Drawer
          side="left"
          open={leftPanelOpen}
          onClose={closePanels}
          labelledBy="appshell-title"
        >
          {left}
        </Drawer>
      ) : null}

      {showRightAsDrawer ? (
        <Drawer
          side="right"
          open={rightPanelOpen}
          onClose={closePanels}
          labelledBy="appshell-title"
        >
          {right}
        </Drawer>
      ) : null}
    </div>
  );
}
