/**
 * Run view types — BRD-13 / IP-13.
 *
 * The backend exposes a snake_case `RunResponse` (see `lib/api.ts`
 * `RunResponseDto`). The client-side `Run` is the camelCase projection
 * used by organisms, plus a derived `RunStatus`.
 */

import type { OutputFormat, QuestionType, StopReason } from "./events";
import type { RunResponseDto } from "@/lib/api";

export type RunStatus = "running" | "stopped";

export interface Run {
  id: string;
  ownerUsername: string;
  question: string;
  userContext: string | null;
  questionType: QuestionType | null;
  outputFormat: OutputFormat;
  confidenceThreshold: number;
  llmProvider: string;
  startedAt: string;
  stoppedAt: string | null;
  stopReason: StopReason | null;
  parentRunId: string | null;
  forkedAtEventId: string | null;
}

export function deriveStatus(dto: Pick<RunResponseDto, "stop_reason" | "stopped_at">): RunStatus {
  if (dto.stop_reason === null && dto.stopped_at === null) {
    return "running";
  }
  return "stopped";
}

export function mapRun(dto: RunResponseDto): Run {
  return {
    id: dto.id,
    ownerUsername: dto.owner_username,
    question: dto.question,
    userContext: dto.user_context,
    questionType: dto.question_type,
    outputFormat: dto.output_format,
    confidenceThreshold: dto.confidence_threshold,
    llmProvider: dto.llm_provider ?? "github",
    startedAt: dto.started_at,
    stoppedAt: dto.stopped_at,
    stopReason: dto.stop_reason,
    parentRunId: dto.parent_run_id,
    forkedAtEventId: dto.forked_at_event_id,
  };
}

export type { RunResponseDto };
