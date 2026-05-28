import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";

import { StopReasonCard, stopReasonConfig } from "./StopReasonCard";
import type { StopReason } from "@/types/events";

const reasons: ReadonlyArray<StopReason> = [
  "judge_confirmed",
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

  it.each<StopReason>(["errored", "user_cancelled"])(
    "renders an inline Resume button when onResume is provided and reason is %s",
    async (reason) => {
      const onResume = vi.fn();
      render(<StopReasonCard reason={reason} onResume={onResume} />);
      const btn = screen.getByTestId("stop-reason-resume-button");
      expect(btn).toBeInTheDocument();
      await userEvent.click(btn);
      expect(onResume).toHaveBeenCalledTimes(1);
    }
  );

  it.each<StopReason>(["judge_confirmed", "stopped_by_budget"])(
    "does not render the Resume button for non-resumable reason %s",
    (reason) => {
      render(<StopReasonCard reason={reason} onResume={vi.fn()} />);
      expect(
        screen.queryByTestId("stop-reason-resume-button")
      ).not.toBeInTheDocument();
    }
  );

  it("hides the Resume button when no onResume handler is passed", () => {
    render(<StopReasonCard reason="errored" />);
    expect(
      screen.queryByTestId("stop-reason-resume-button")
    ).not.toBeInTheDocument();
  });
});
