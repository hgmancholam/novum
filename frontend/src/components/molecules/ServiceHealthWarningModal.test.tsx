import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";

import { ServiceHealthWarningModal } from "./ServiceHealthWarningModal";
import type { ServiceHealth } from "@/types/health";

const SERVICES: ServiceHealth[] = [
  {
    id: "anthropic",
    name: "Anthropic",
    category: "llm",
    status: "no_key",
    latency_ms: null,
    message: null,
    checked_at: "2026-06-01T00:00:00Z",
  },
  {
    id: "tavily",
    name: "Tavily",
    category: "search",
    status: "down",
    latency_ms: null,
    message: "Connection refused",
    checked_at: "2026-06-01T00:00:00Z",
  },
];

describe("ServiceHealthWarningModal", () => {
  it("renders the list of affected services with status labels", () => {
    render(<ServiceHealthWarningModal services={SERVICES} onClose={vi.fn()} />);
    expect(screen.getByText("Anthropic")).toBeInTheDocument();
    expect(screen.getByText("not configured")).toBeInTheDocument();
    expect(screen.getByText("Tavily")).toBeInTheDocument();
    expect(screen.getByText("unreachable")).toBeInTheDocument();
  });

  it("calls onClose when the X button is clicked", async () => {
    const onClose = vi.fn();
    render(<ServiceHealthWarningModal services={SERVICES} onClose={onClose} />);
    await userEvent.click(screen.getByTestId("svc-warning-close"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose when the dismiss button is clicked", async () => {
    const onClose = vi.fn();
    render(<ServiceHealthWarningModal services={SERVICES} onClose={onClose} />);
    await userEvent.click(screen.getByTestId("svc-warning-dismiss"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose when the backdrop is clicked", async () => {
    const onClose = vi.fn();
    render(<ServiceHealthWarningModal services={SERVICES} onClose={onClose} />);
    await userEvent.click(screen.getByTestId("svc-warning-backdrop"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("has no axe violations", async () => {
    const { container } = render(
      <ServiceHealthWarningModal services={SERVICES} onClose={vi.fn()} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
