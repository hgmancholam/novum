/**
 * Event types generated from backend Pydantic models.
 * DO NOT EDIT MANUALLY - run scripts/export_types.py to regenerate.
 */

// Placeholder - will be generated from backend models
export interface RunEvent {
  id: string;
  run_id: string;
  parent_event_id: string | null;
  step_index: number;
  type: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export type StopReason =
  | "judge_confirmed"
  | "honest_unanswerable"
  | "honest_contradiction"
  | "honest_ambiguous"
  | "stopped_by_budget"
  | "user_cancelled"
  | "errored";

export type QuestionType =
  | "factual"
  | "comparative"
  | "definitional"
  | "state_of_art"
  | "causal";

export type OutputFormat = "prose" | "structured";

export interface Run {
  id: string;
  owner_username: string;
  question: string;
  user_context: string | null;
  output_format: OutputFormat;
  confidence_threshold: number;
  question_type: QuestionType | null;
  stop_reason: StopReason | null;
  parent_run_id: string | null;
  forked_at_event_id: string | null;
  created_at: string;
  updated_at: string;
}
