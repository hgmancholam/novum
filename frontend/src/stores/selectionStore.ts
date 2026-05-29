/**
 * Selection state store for cross-component UI selection and panel visibility.
 * See ui-prototype.md §8.3 (folder structure) and BRD-11 §4.6.
 *
 * IP-24 Phase 5: Added isTracePanelCollapsed for right-panel minimize.
 */

import { create } from "zustand";

const TRACE_PANEL_COLLAPSED_KEY = "novum_trace_panel_collapsed";

function getInitialTracePanelCollapsed(): boolean {
  try {
    return localStorage.getItem(TRACE_PANEL_COLLAPSED_KEY) === "1";
  } catch {
    return false;
  }
}

function persistTracePanelCollapsed(value: boolean): void {
  try {
    localStorage.setItem(TRACE_PANEL_COLLAPSED_KEY, value ? "1" : "0");
  } catch {
    // Ignore storage errors
  }
}

export interface SelectionState {
  selectedRunId: string | null;
  setSelectedRunId: (id: string | null) => void;

  selectedEventId: number | null;
  setSelectedEventId: (id: number | null) => void;

  leftPanelOpen: boolean;
  rightPanelOpen: boolean;
  openLeftPanel: () => void;
  openRightPanel: () => void;
  toggleLeftPanel: () => void;
  toggleRightPanel: () => void;
  closePanels: () => void;

  /** IP-24 Phase 5: Trace panel collapsed state (persisted). */
  isTracePanelCollapsed: boolean;
  toggleTracePanelCollapsed: () => void;

  /** Reset all selection state (called on logout). */
  reset: () => void;
}

export const useSelectionStore = create<SelectionState>((set) => ({
  selectedRunId: null,
  setSelectedRunId: (id) => {
    set({ selectedRunId: id });
  },

  selectedEventId: null,
  setSelectedEventId: (id) => {
    set({ selectedEventId: id });
  },

  leftPanelOpen: false,
  rightPanelOpen: false,
  openLeftPanel: () => {
    set({ leftPanelOpen: true });
  },
  openRightPanel: () => {
    set({ rightPanelOpen: true });
  },
  toggleLeftPanel: () => {
    set((state) => ({ leftPanelOpen: !state.leftPanelOpen }));
  },
  toggleRightPanel: () => {
    set((state) => ({ rightPanelOpen: !state.rightPanelOpen }));
  },
  closePanels: () => {
    set({ leftPanelOpen: false, rightPanelOpen: false });
  },

  // IP-24 Phase 5
  isTracePanelCollapsed: getInitialTracePanelCollapsed(),
  toggleTracePanelCollapsed: () => {
    set((state) => {
      const newValue = !state.isTracePanelCollapsed;
      persistTracePanelCollapsed(newValue);
      return { isTracePanelCollapsed: newValue };
    });
  },

  reset: () => {
    set({
      selectedRunId: null,
      selectedEventId: null,
      leftPanelOpen: false,
      rightPanelOpen: false,
      isTracePanelCollapsed: false,
    });
  },
}));
