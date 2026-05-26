import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";

import { StopReasonCard, stopReasonConfig } from "./StopReasonCard";
import type { StopReason } from "@/types/events";

const reasons: ReadonlyArray<StopReason> = [
  "judge_confirmed",
  "honest_unanswerable",
  "honest_contradiction",
  "honest_ambiguous",
  "stopped_by_budget",
  "user_cancelled",
  "errored",
];

describe("StopReasonCard", () => {
  it.each(reasons)(
    "renders title, description and correct variant for %s",
    (reason) => {
      render(<StopReasonCard reason={reason} />);
      const card = screen.getByTestId("stop-reason-card");
      const config = stopReasonConfig[reason];
      expect(card).toHaveAttribute("data-reason", reason);
      expect(card).toHaveAttribute("data-variant", config.variant);
      expect(screen.getByText(config.title)).toBeInTheDocument();
      expect(screen.getByText(config.description)).toBeInTheDocument();
    }
  );

  it("renders the optional explanation when provided", () => {
    render(
      <StopReasonCard
        reason="errored"
        explanation="Upstream LLM provider returned 503."
      />
    );
    expect(
      screen.getByText("Upstream LLM provider returned 503.")
    ).toBeInTheDocument();
  });

  it("has no accessibility violations for every variant", async () => {
    for (const reason of reasons) {
      const { container, unmount } = render(<StopReasonCard reason={reason} />);
      const results = await axe(container);
      expect(results).toHaveNoViolations();
      unmount();
    }
  });
});
