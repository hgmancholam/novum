import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { EventIcon } from "./EventIcon";

describe("EventIcon", () => {
  it("renders an svg with aria-hidden and a tone marker", () => {
    render(<EventIcon type="JudgeRuled" />);
    const icon = screen.getByTestId("event-icon");
    expect(icon).toBeInTheDocument();
    expect(icon).toHaveAttribute("aria-hidden", "true");
    expect(icon.getAttribute("data-tone")).toBe("judge");
    expect(icon.getAttribute("data-event-type")).toBe("JudgeRuled");
  });

  it("falls back to neutral for unknown event types", () => {
    render(<EventIcon type="totally-fake-type" />);
    const icon = screen.getByTestId("event-icon");
    expect(icon.getAttribute("data-tone")).toBe("neutral");
  });

  it("honors the size prop", () => {
    render(<EventIcon type="QuestionAsked" size={24} />);
    const icon = screen.getByTestId("event-icon");
    expect(icon.getAttribute("width")).toBe("24");
    expect(icon.getAttribute("height")).toBe("24");
  });
});
