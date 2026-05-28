import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { axe } from "jest-axe";
import { CollapseToggleButton } from "./CollapseToggleButton";

describe("CollapseToggleButton", () => {
  const labelCollapse = "Collapse section";
  const labelExpand = "Expand section";

  it("renders with aria-expanded=false when collapsed", () => {
    render(
      <CollapseToggleButton
        isCollapsed={true}
        onToggle={vi.fn()}
        labelCollapse={labelCollapse}
        labelExpand={labelExpand}
      />
    );
    const button = screen.getByRole("button");
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(button).toHaveAttribute("aria-label", labelExpand);
  });

  it("renders with aria-expanded=true when expanded", () => {
    render(
      <CollapseToggleButton
        isCollapsed={false}
        onToggle={vi.fn()}
        labelCollapse={labelCollapse}
        labelExpand={labelExpand}
      />
    );
    const button = screen.getByRole("button");
    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(button).toHaveAttribute("aria-label", labelCollapse);
  });

  it("calls onToggle when clicked", async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();
    render(
      <CollapseToggleButton
        isCollapsed={true}
        onToggle={onToggle}
        labelCollapse={labelCollapse}
        labelExpand={labelExpand}
      />
    );
    await user.click(screen.getByRole("button"));
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("merges custom className", () => {
    render(
      <CollapseToggleButton
        isCollapsed={true}
        onToggle={vi.fn()}
        labelCollapse={labelCollapse}
        labelExpand={labelExpand}
        className="custom-toggle"
      />
    );
    const button = screen.getByRole("button");
    expect(button.className).toContain("custom-toggle");
  });

  it("has no a11y violations", async () => {
    const { container } = render(
      <CollapseToggleButton
        isCollapsed={false}
        onToggle={vi.fn()}
        labelCollapse={labelCollapse}
        labelExpand={labelExpand}
      />
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
