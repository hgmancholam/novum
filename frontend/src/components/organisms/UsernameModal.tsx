/**
 * UsernameModal organism (BRD-04 §4.9).
 *
 * Token-only styling per ui-prototype.md §1.3 (no hardcoded color classes).
 * Uses the `Button` atom for actions.
 */

import { useState, type SyntheticEvent } from "react";

import { Button } from "@/components/atoms";
import { useUserStore } from "@/stores/userStore";

export interface UsernameModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function UsernameModal({ isOpen, onClose }: UsernameModalProps) {
  const [username, setUsername] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const register = useUserStore((state) => state.register);
  const isAuthenticated = useUserStore((state) => state.isAuthenticated);

  if (!isOpen) {
    return null;
  }

  const submit = async (e: SyntheticEvent): Promise<void> => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);
    try {
      await register(username.trim());
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e: SyntheticEvent): void => {
    void submit(e);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="username-modal-title"
      aria-describedby="username-modal-description"
      data-testid="username-modal"
      className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--overlay-scrim)]"
    >
      <div
        data-testid="username-modal-surface"
        className="w-full max-w-md rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--bg-secondary)] p-6 shadow-[0_8px_32px_rgba(0,0,0,0.4)]"
      >
        <h2
          id="username-modal-title"
          className="mb-2 text-xl font-semibold text-[var(--text-primary)]"
        >
          Choose a Username
        </h2>
        <p
          id="username-modal-description"
          className="mb-4 text-sm text-[var(--text-secondary)]"
        >
          Your username is your identity. No email or password required.
        </p>

        <form onSubmit={handleSubmit}>
          <label htmlFor="username-input" className="sr-only">
            Username
          </label>
          <input
            id="username-input"
            type="text"
            value={username}
            onChange={(e) => {
              setUsername(e.target.value);
            }}
            placeholder="Enter username (3-50 chars)"
            className="mb-2 w-full rounded-[var(--radius-sm)] border border-[var(--glass-border)] bg-[var(--bg-primary)] px-3 py-2 text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
            minLength={3}
            maxLength={50}
            pattern="[a-zA-Z0-9_-]+"
            required
            disabled={isLoading}
          />

          {error !== null && (
            <p
              role="alert"
              className="mb-2 text-sm text-[var(--semantic-error)]"
            >
              {error}
            </p>
          )}

          <div className="mt-4 flex gap-2">
            {isAuthenticated ? (
              <Button
                type="button"
                variant="ghost"
                size="md"
                onClick={onClose}
                disabled={isLoading}
                className="flex-1"
              >
                Cancel
              </Button>
            ) : null}
            <Button
              type="submit"
              variant="primary"
              size="md"
              loading={isLoading}
              disabled={username.trim().length < 3}
              className="flex-1"
            >
              {isLoading ? "Creating..." : "Create Identity"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
