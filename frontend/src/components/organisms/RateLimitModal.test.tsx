import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { axe } from "jest-axe";

import { RateLimitModal } from "./RateLimitModal";
import {
  RATE_LIMIT_MODAL_CLOSE,
  RATE_LIMIT_MODAL_DESCRIPTION,
  RATE_LIMIT_MODAL_TITLE,
} from "@/lib/microcopy";

describe("RateLimitModal", () => {
  it("renders nothing when closed", () => {
    const { container } = render(
      <RateLimitModal isOpen={false} onClose={vi.fn()} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders title, description and close button when open", () => {
    render(<RateLimitModal isOpen onClose={vi.fn()} />);
    expect(screen.getByText(RATE_LIMIT_MODAL_TITLE)).toBeInTheDocument();
    expect(screen.getByText(RATE_LIMIT_MODAL_DESCRIPTION)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: RATE_LIMIT_MODAL_CLOSE })
    ).toBeInTheDocument();
  });

  it("calls onClose when the close button is clicked", () => {
    const onClose = vi.fn();
    render(<RateLimitModal isOpen onClose={onClose} />);
    fireEvent.click(screen.getByTestId("rate-limit-modal-close"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose on Escape", () => {
    const onClose = vi.fn();
    render(<RateLimitModal isOpen onClose={onClose} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when clicking the backdrop", () => {
    const onClose = vi.fn();
    render(<RateLimitModal isOpen onClose={onClose} />);
    fireEvent.click(screen.getByTestId("rate-limit-modal"));
    expect(onClose).toHaveBeenCalled();
  });

  it("does NOT call onClose when clicking the inner surface", () => {
    const onClose = vi.fn();
    render(<RateLimitModal isOpen onClose={onClose} />);
    fireEvent.click(screen.getByTestId("rate-limit-modal-surface"));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<RateLimitModal isOpen onClose={vi.fn()} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
