import { describe, it, expect } from "vitest";

import { mapRun, deriveStatus } from "./run";
import type { RunResponseDto } from "@/lib/api";

function dto(overrides: Partial<RunResponseDto> = {}): RunResponseDto {
  return {
    id: "00000000-0000-0000-0000-000000000001",
    owner_username: "alice",
    question: "Q?",
    user_context: null,
    question_type: "factual",
    output_format: "prose",
    confidence_threshold: 0.7,
    started_at: "2026-05-26T00:00:00Z",
    stopped_at: null,
    stop_reason: null,
    parent_run_id: null,
    forked_at_event_id: null,
    llm_provider: "github",
    ...overrides,
  };
}

describe("mapRun", () => {
  it("maps snake_case dto to camelCase Run", () => {
    const run = mapRun(
      dto({
        owner_username: "bob",
        user_context: "extra",
        confidence_threshold: 0.9,
        parent_run_id: "parent",
        forked_at_event_id: "event",
      })
    );
    expect(run.ownerUsername).toBe("bob");
    expect(run.userContext).toBe("extra");
    expect(run.confidenceThreshold).toBe(0.9);
    expect(run.parentRunId).toBe("parent");
    expect(run.forkedAtEventId).toBe("event");
  });
});

describe("deriveStatus", () => {
  it("returns 'running' when stop_reason and stopped_at are both null", () => {
    expect(deriveStatus({ stop_reason: null, stopped_at: null })).toBe(
      "running"
    );
  });

  it("returns 'stopped' when a stop_reason is present", () => {
    expect(
      deriveStatus({
        stop_reason: "judge_confirmed",
        stopped_at: "2026-05-26T00:00:00Z",
      })
    ).toBe("stopped");
  });

  it("returns 'stopped' when stopped_at is set even if stop_reason is null", () => {
    expect(
      deriveStatus({ stop_reason: null, stopped_at: "2026-05-26T00:00:00Z" })
    ).toBe("stopped");
  });
});
