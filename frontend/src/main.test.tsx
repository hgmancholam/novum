import { describe, it, expect, beforeEach, vi } from "vitest";
import { render } from "@testing-library/react";
import { AppBoot, __resetAppBootForTests } from "./main";
import { useUserStore } from "@/stores/userStore";

describe("AppBoot", () => {
  beforeEach(() => {
    __resetAppBootForTests();
    useUserStore.setState({
      user: null,
      isVerifying: false,
      isAuthenticated: false,
    });
  });

  it("calls useUserStore.initialize exactly once across two mounts (StrictMode-safe)", () => {
    const initialize = vi
      .fn<() => Promise<void>>()
      .mockResolvedValue();
    useUserStore.setState({ initialize });

    const first = render(
      <AppBoot>
        <div data-testid="boot-child-a">A</div>
      </AppBoot>
    );
    first.unmount();
    render(
      <AppBoot>
        <div data-testid="boot-child-b">B</div>
      </AppBoot>
    );

    expect(initialize).toHaveBeenCalledTimes(1);
  });

  it("renders children and the UsernameModalContainer as siblings", () => {
    useUserStore.setState({
      user: null,
      isVerifying: false,
      isAuthenticated: false,
    });
    const { getByTestId } = render(
      <AppBoot>
        <div data-testid="boot-child">child</div>
      </AppBoot>
    );
    expect(getByTestId("boot-child")).toBeInTheDocument();
    expect(getByTestId("username-modal")).toBeInTheDocument();
  });
});
