/**
 * UsernameModalContainer organism — global, route-independent mount
 * point for the `UsernameModal`.
 *
 * Auto-open contract (IP-11 iter 2 §4.2):
 *   open := (!isVerifying && !isAuthenticated) || useLoginModal.isOpen
 *
 * `onClose` is a no-op while unauthenticated (there is no guest mode
 * in V1 — see BRD-04 §4.9 strict reading). When the user is
 * authenticated, closing dismisses the manually-triggered open via
 * `useLoginModal.close()`.
 */

import { UsernameModal } from "@/components/organisms/UsernameModal";
import { useLoginModal } from "@/hooks/useLoginModal";
import { useUserStore } from "@/stores/userStore";

const NOOP = (): void => {
  /* no-op: modal stays open until the user registers */
};

export function UsernameModalContainer() {
  const isVerifying = useUserStore((s) => s.isVerifying);
  const isAuthenticated = useUserStore((s) => s.isAuthenticated);
  const loginModalIsOpen = useLoginModal((s) => s.isOpen);
  const closeLoginModal = useLoginModal((s) => s.close);

  const autoOpen = !isVerifying && !isAuthenticated;
  const isOpen = autoOpen || loginModalIsOpen;
  const onClose = isAuthenticated ? closeLoginModal : NOOP;

  return <UsernameModal isOpen={isOpen} onClose={onClose} />;
}
