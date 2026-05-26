/**
 * UsernameModal organism (BRD-04 §4.9).
 *
 * Lets the user create an identity. On success the modal closes; on
 * failure the error message from the backend is shown inline.
 */

import { useState, type FormEvent } from "react";

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

  if (!isOpen) {
    return null;
  }

  const handleSubmit = async (e: FormEvent) => {
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

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="username-modal-title"
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
    >
      <div className="bg-white dark:bg-neutral-900 rounded-lg p-6 w-full max-w-md">
        <h2 id="username-modal-title" className="text-xl font-semibold mb-4">
          Choose a Username
        </h2>
        <p className="text-sm text-neutral-600 dark:text-neutral-400 mb-4">
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
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Enter username (3-50 chars)"
            className="w-full px-3 py-2 border rounded-md mb-2 dark:bg-neutral-800 dark:border-neutral-700"
            minLength={3}
            maxLength={50}
            pattern="[a-zA-Z0-9_-]+"
            required
            disabled={isLoading}
          />

          {error !== null && (
            <p role="alert" className="text-red-500 text-sm mb-2">
              {error}
            </p>
          )}

          <div className="flex gap-2 mt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border rounded-md hover:bg-neutral-100 dark:hover:bg-neutral-800"
              disabled={isLoading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
              disabled={isLoading || username.trim().length < 3}
            >
              {isLoading ? "Creating..." : "Create Identity"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
