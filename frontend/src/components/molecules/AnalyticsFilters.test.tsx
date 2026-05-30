import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AnalyticsFilters } from "./AnalyticsFilters";

describe("AnalyticsFilters", () => {
  it("calls onChange when a provider chip is toggled", async () => {
    const onChange = vi.fn();
    render(
      <AnalyticsFilters
        filters={{}}
        onChange={onChange}
        providers={["anthropic", "openai"]}
        kinds={["llm"]}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: /anthropic/i }));
    expect(onChange).toHaveBeenCalledWith({ providers: ["anthropic"] });
  });

  it("removes the provider when toggled off", async () => {
    const onChange = vi.fn();
    render(
      <AnalyticsFilters
        filters={{ providers: ["anthropic"] }}
        onChange={onChange}
        providers={["anthropic", "openai"]}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: /anthropic/i }));
    expect(onChange).toHaveBeenCalledWith({});
  });

  it("emits dateFrom on date input change", async () => {
    const onChange = vi.fn();
    render(<AnalyticsFilters filters={{}} onChange={onChange} />);
    const from = screen.getByLabelText("From");
    await userEvent.type(from, "2026-05-01");
    expect(onChange).toHaveBeenLastCalledWith({ dateFrom: "2026-05-01" });
  });

  it("shows Reset only when filters are active and calls onReset", async () => {
    const onReset = vi.fn();
    const { rerender } = render(
      <AnalyticsFilters filters={{}} onChange={() => {}} onReset={onReset} />
    );
    expect(screen.queryByRole("button", { name: /reset/i })).toBeNull();

    rerender(
      <AnalyticsFilters
        filters={{ providers: ["anthropic"] }}
        onChange={() => {}}
        onReset={onReset}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: /reset/i }));
    expect(onReset).toHaveBeenCalledTimes(1);
  });

  it("calls onRefresh when Refresh is clicked", async () => {
    const onRefresh = vi.fn();
    render(
      <AnalyticsFilters
        filters={{}}
        onChange={() => {}}
        onRefresh={onRefresh}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: /refresh/i }));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });
});
