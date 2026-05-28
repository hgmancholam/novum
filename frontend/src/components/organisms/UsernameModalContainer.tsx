/**
 * UsernameModalContainer organism — global, route-independent mount
 * point for the `UsernameModal`.
 *
 * Auto-open contract (IP-11 iter 2 §4.2):
 *   open := (!isVerifying && !isAuthenticated && !isPublicRoute) || useLoginModal.isOpen
 *
 * Public routes (currently `/` = HowWeWorkPage) suppress the auto-open
 * so unauthenticated visitors can read the marketing page without being
 * blocked by the login modal. Manual `useLoginModal.open()` still works
 * everywhere.
 *
 * `onClose` is a no-op while unauthenticated (there is no guest mode
 * in V1 — see BRD-04 §4.9 strict reading). When the user is
 * authenticated, closing dismisses the manually-triggered open via
 * `useLoginModal.close()`.
 */

import { UsernameModal } from "@/components/organisms/UsernameModal";
import { useLoginModal } from "@/hooks/useLoginModal";
import { usePathname } from "@/hooks/usePathname";
import { useUserStore } from "@/stores/userStore";

const PUBLIC_ROUTES: ReadonlySet<string> = new Set(["/"]);

const NOOP = (): void => {
  /* no-op: modal stays open until the user registers */
};

export function UsernameModalContainer() {
  const isVerifying = useUserStore((s) => s.isVerifying);
  const isAuthenticated = useUserStore((s) => s.isAuthenticated);
  const loginModalIsOpen = useLoginModal((s) => s.isOpen);
  const closeLoginModal = useLoginModal((s) => s.close);
  const pathname = usePathname();

  const isPublicRoute = PUBLIC_ROUTES.has(pathname);
  const autoOpen = !isVerifying && !isAuthenticated && !isPublicRoute;
  const isOpen = autoOpen || loginModalIsOpen;
  const onClose = isAuthenticated ? closeLoginModal : NOOP;

  return <UsernameModal isOpen={isOpen} onClose={onClose} />;
}
