import { describe, it, expect, beforeEach } from "vitest";
import { useSelectionStore } from "./selectionStore";

function resetStore(): void {
  useSelectionStore.setState({
    selectedRunId: null,
    selectedEventId: null,
    leftPanelOpen: false,
    rightPanelOpen: false,
  });
}

describe("selectionStore", () => {
  beforeEach(() => {
    resetStore();
  });

  it("has the documented initial state", () => {
    const s = useSelectionStore.getState();
    expect(s.selectedRunId).toBeNull();
    expect(s.selectedEventId).toBeNull();
    expect(s.leftPanelOpen).toBe(false);
    expect(s.rightPanelOpen).toBe(false);
  });

  it("setSelectedRunId updates the value", () => {
    useSelectionStore.getState().setSelectedRunId("run-123");
    expect(useSelectionStore.getState().selectedRunId).toBe("run-123");
    useSelectionStore.getState().setSelectedRunId(null);
    expect(useSelectionStore.getState().selectedRunId).toBeNull();
  });

  it("setSelectedEventId updates the value", () => {
    useSelectionStore.getState().setSelectedEventId(42);
    expect(useSelectionStore.getState().selectedEventId).toBe(42);
  });

  it("openLeftPanel / openRightPanel set the flags", () => {
    useSelectionStore.getState().openLeftPanel();
    useSelectionStore.getState().openRightPanel();
    const s = useSelectionStore.getState();
    expect(s.leftPanelOpen).toBe(true);
    expect(s.rightPanelOpen).toBe(true);
  });

  it("toggleLeftPanel flips the flag", () => {
    useSelectionStore.getState().toggleLeftPanel();
    expect(useSelectionStore.getState().leftPanelOpen).toBe(true);
    useSelectionStore.getState().toggleLeftPanel();
    expect(useSelectionStore.getState().leftPanelOpen).toBe(false);
  });

  it("toggleRightPanel flips the flag", () => {
    useSelectionStore.getState().toggleRightPanel();
    expect(useSelectionStore.getState().rightPanelOpen).toBe(true);
    useSelectionStore.getState().toggleRightPanel();
    expect(useSelectionStore.getState().rightPanelOpen).toBe(false);
  });

  it("closePanels resets both flags", () => {
    useSelectionStore.setState({
      leftPanelOpen: true,
      rightPanelOpen: true,
    });
    useSelectionStore.getState().closePanels();
    const s = useSelectionStore.getState();
    expect(s.leftPanelOpen).toBe(false);
    expect(s.rightPanelOpen).toBe(false);
  });

  it("reset clears all selection state", () => {
    useSelectionStore.setState({
      selectedRunId: "run-99",
      selectedEventId: 7,
      leftPanelOpen: true,
      rightPanelOpen: true,
    });
    useSelectionStore.getState().reset();
    const s = useSelectionStore.getState();
    expect(s.selectedRunId).toBeNull();
    expect(s.selectedEventId).toBeNull();
    expect(s.leftPanelOpen).toBe(false);
    expect(s.rightPanelOpen).toBe(false);
  });
});
