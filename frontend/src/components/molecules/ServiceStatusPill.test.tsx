import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { axe } from "jest-axe";

import { ServiceStatusPill } from "./ServiceStatusPill";
import type { ServiceHealth } from "@/types/health";

function makeService(overrides: Partial<ServiceHealth> = {}): ServiceHealth {
  return {
    id: "anthropic",
    name: "Anthropic",
    category: "llm",
    status: "ok",
    latency_ms: 245,
    message: null,
    checked_at: "2026-06-01T00:00:00Z",
    ...overrides,
  };
}

describe("ServiceStatusPill", () => {
  it("renders the service name", () => {
    render(<ServiceStatusPill service={makeService()} />);
    expect(screen.getByText("Anthropic")).toBeInTheDocument();
  });

  it("uses '{name}: {status}, {latency_ms}ms' when ok and latency known", () => {
    render(<ServiceStatusPill service={makeService({ status: "ok", latency_ms: 200 })} />);
    const pill = screen.getByTestId("service-status-pill");
    expect(pill).toHaveAttribute("aria-label", "Anthropic: ok, 200ms");
  });

  it("uses '{name}: {status}, {latency_ms}ms' when degraded", () => {
    render(
      <ServiceStatusPill
        service={makeService({ status: "degraded", latency_ms: 1800 })}
      />,
    );
    expect(screen.getByTestId("service-status-pill")).toHaveAttribute(
      "aria-label",
      "Anthropic: degraded, 1800ms",
    );
  });

  it("appends the upstream message for failure states", () => {
    render(
      <ServiceStatusPill
        service={makeService({ status: "down", latency_ms: null, message: "auth error" })}
      />,
    );
    expect(screen.getByTestId("service-status-pill")).toHaveAttribute(
      "aria-label",
      "Anthropic: down — auth error",
    );
  });

  it("falls back to '{name}: {status}' for disabled", () => {
    render(
      <ServiceStatusPill
        service={makeService({
          id: "openai",
          name: "OpenAI",
          status: "disabled",
          latency_ms: null,
          message: null,
        })}
      />,
    );
    expect(screen.getByTestId("service-status-pill")).toHaveAttribute(
      "aria-label",
      "OpenAI: disabled",
    );
  });

  it("mirrors aria-label into title for hover tooltips", () => {
    render(<ServiceStatusPill service={makeService({ status: "ok", latency_ms: 100 })} />);
    const pill = screen.getByTestId("service-status-pill");
    expect(pill).toHaveAttribute("title", pill.getAttribute("aria-label"));
  });

  it("has no axe violations", async () => {
    const { container } = render(<ServiceStatusPill service={makeService()} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
