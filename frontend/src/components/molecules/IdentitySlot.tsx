/**
 * IdentitySlot molecule — TopBar identity indicator.
 * See IP-11 iter 2 §4.3 (T4) and ui-prototype.md §2 / §3.2.
 *
 * Reads auth state from `userStore` and the login-modal signal from
 * `useLoginModal`. Props-free by design — it is mounted in the
 * `AppShell` TopBar and needs no configuration.
 */

import { Badge, Button, Spinner } from "@/components/atoms";
import { useLoginModal } from "@/hooks/useLoginModal";
import { useUserStore } from "@/stores/userStore";

export function IdentitySlot() {
  const isVerifying = useUserStore((s) => s.isVerifying);
  const isAuthenticated = useUserStore((s) => s.isAuthenticated);
  const username = useUserStore((s) => s.user?.username ?? null);
  const logout = useUserStore((s) => s.logout);
  const openLoginModal = useLoginModal((s) => s.open);

  if (isVerifying) {
    return (
      <div
        data-testid="identity-slot"
        data-state="verifying"
        className="flex items-center"
      >
        <Spinner size="sm" label="Verifying session" />
      </div>
    );
  }

  if (!isAuthenticated || username === null) {
    return (
      <div
        data-testid="identity-slot"
        data-state="anonymous"
        className="flex items-center"
      >
        <Button
          variant="primary"
          size="sm"
          onClick={() => {
            openLoginModal();
          }}
        >
          Sign in
        </Button>
      </div>
    );
  }

  return (
    <div
      data-testid="identity-slot"
      data-state="authenticated"
      className="flex items-center gap-2"
    >
      <Badge variant="secondary">{username}</Badge>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => {
          logout();
        }}
      >
        Logout
      </Button>
    </div>
  );
}
