/**
 * Selection state store for cross-component UI selection and panel visibility.
 * See ui-prototype.md §8.3 (folder structure) and BRD-11 §4.6.
 */

import { create } from "zustand";

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
}));
