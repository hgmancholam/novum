import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { axe } from "jest-axe";
import { UsernameModal } from "./UsernameModal";
import { useUserStore } from "@/stores/userStore";

function resetStore(): void {
  useUserStore.setState({
    user: null,
    isVerifying: false,
    isAuthenticated: false,
  });
}

describe("UsernameModal", () => {
  beforeEach(() => {
    resetStore();
  });

  it("renders nothing when isOpen is false", () => {
    const { container } = render(
      <UsernameModal isOpen={false} onClose={() => {}} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the dialog with token-based classes (no hardcoded colors)", () => {
    render(<UsernameModal isOpen onClose={() => {}} />);
    const surface = screen.getByTestId("username-modal-surface");
    const html = surface.outerHTML;
    expect(html).not.toMatch(/\bbg-white\b/);
    expect(html).not.toMatch(/\bbg-black\b/);
    expect(html).not.toMatch(/\btext-neutral-/);
    expect(html).not.toMatch(/\bdark:bg-neutral-/);
    expect(html).toMatch(/data-variant="default"/);
  });

  it("uses the overlay-scrim token on the backdrop", () => {
    render(<UsernameModal isOpen onClose={() => {}} />);
    const dialog = screen.getByTestId("username-modal");
    expect(dialog.className).toMatch(/--overlay-scrim/);
  });

  it("does not render Cancel when unauthenticated (no guest mode)", () => {
    render(<UsernameModal isOpen onClose={() => {}} />);
    expect(
      screen.queryByRole("button", { name: "Cancel" })
    ).not.toBeInTheDocument();
  });

  it("renders Cancel when authenticated (manual re-open path)", () => {
    useUserStore.setState({
      user: { username: "bob", token: "tok" },
      isVerifying: false,
      isAuthenticated: true,
    });
    render(<UsernameModal isOpen onClose={() => {}} />);
    expect(
      screen.getByRole("button", { name: "Cancel" })
    ).toBeInTheDocument();
  });

  it("submit calls register and then onClose on success", async () => {
    const register = vi
      .fn<(username: string) => Promise<void>>()
      .mockResolvedValue();
    useUserStore.setState({ register });
    const onClose = vi.fn();
    render(<UsernameModal isOpen onClose={onClose} />);
    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "alice" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create Identity" }));
    await waitFor(() => {
      expect(register).toHaveBeenCalledWith("alice");
    });
    await waitFor(() => {
      expect(onClose).toHaveBeenCalled();
    });
  });

  it("shows error message on register rejection", async () => {
    const register = vi
      .fn<(username: string) => Promise<void>>()
      .mockRejectedValue(new Error("Username already exists"));
    useUserStore.setState({ register });
    render(<UsernameModal isOpen onClose={() => {}} />);
    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "alice" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create Identity" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Username already exists"
    );
  });

  it("has no a11y violations", async () => {
    const { container } = render(
      <UsernameModal isOpen onClose={() => {}} />
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
