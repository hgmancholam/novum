import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { StatusBadge } from "./StatusBadge";
import type { StopReason } from "@/types/events";

const cases: ReadonlyArray<{
  reason: StopReason;
  label: string;
  variant: string;
}> = [
  { reason: "judge_confirmed", label: "Judge confirmed", variant: "success" },
  {
    reason: "honest_unanswerable",
    label: "Honest stop — unanswerable",
    variant: "warning",
  },
  {
    reason: "honest_contradiction",
    label: "Honest stop — contradiction",
    variant: "warning",
  },
  {
    reason: "honest_ambiguous",
    label: "Honest stop — ambiguous",
    variant: "warning",
  },
  { reason: "stopped_by_budget", label: "Stopped on budget", variant: "warning" },
  { reason: "user_cancelled", label: "Cancelled", variant: "secondary" },
  { reason: "errored", label: "Errored", variant: "error" },
];

describe("StatusBadge", () => {
  it("renders Researching… with info variant when status=running", () => {
    render(<StatusBadge status="running" />);
    const el = screen.getByText("Researching…");
    expect(el).toHaveAttribute("data-variant", "info");
  });

  it.each(cases)(
    "maps stop_reason=$reason → label=$label / variant=$variant",
    ({ reason, label, variant }) => {
      render(<StatusBadge status="completed" stopReason={reason} />);
      const el = screen.getByText(label);
      expect(el).toHaveAttribute("data-variant", variant);
    }
  );

  it("appends errorReason after 'Errored —' when provided", () => {
    render(
      <StatusBadge
        status="stopped"
        stopReason="errored"
        errorReason="provider rate_limit"
      />
    );
    expect(
      screen.getByText("Errored — provider rate_limit")
    ).toBeInTheDocument();
  });

  it("ignores errorReason for non-errored stop reasons", () => {
    render(
      <StatusBadge
        status="completed"
        stopReason="judge_confirmed"
        errorReason="ignored"
      />
    );
    expect(screen.getByText("Judge confirmed")).toBeInTheDocument();
    expect(screen.queryByText(/—/)).not.toBeInTheDocument();
  });

  it("falls back to Unknown when completed without stop_reason", () => {
    render(<StatusBadge status="completed" />);
    const el = screen.getByText("Unknown");
    expect(el).toHaveAttribute("data-variant", "default");
  });

  it("has no a11y violations", async () => {
    const { container } = render(
      <StatusBadge status="completed" stopReason="judge_confirmed" />
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
