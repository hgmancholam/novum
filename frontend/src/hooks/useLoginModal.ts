/**
 * useLoginModal — tiny shared signal for forcing the login modal open
 * even when the auto-open condition (`!isVerifying && !isAuthenticated`)
 * is false. See IP-11 iter 2 §4.4.
 *
 * Backed by a Zustand store so the `Sign in` button in the TopBar and the
 * `UsernameModalContainer` share state without prop drilling. Consistent
 * with the project's "Zustand as shared signal" precedent (`userStore`,
 * `selectionStore`).
 */

import { create } from "zustand";

interface LoginModalState {
  isOpen: boolean;
  open: () => void;
  close: () => void;
}

export const useLoginModal = create<LoginModalState>((set) => ({
  isOpen: false,
  open: () => {
    set({ isOpen: true });
  },
  close: () => {
    set({ isOpen: false });
  },
}));
