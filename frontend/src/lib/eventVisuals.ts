/**
 * Event visual mapping — single source of truth for icon + tone per
 * `EventType`. Lives in `lib/` so atoms/molecules/organisms can consume it.
 * See IP-14 §3.6 and ui-prototype.md §3.3 (icon table).
 */

import type { LucideIcon } from "lucide-react";
import {
  AlertCircle,
  AlertOctagon,
  AlertTriangle,
  BookText,
  Brain,
  CheckCircle2,
  ClipboardCheck,
  Compass,
  Download,
  Eye,
  FilePen,
  FileText,
  FileWarning,
  Flag,
  Gavel,
  GitBranch,
  HelpCircle,
  Lightbulb,
  MessageSquare,
  MessageSquareWarning,
  MinusCircle,
  RotateCw,
  Recycle,
  RefreshCw,
  Repeat,
  Search,
  ShieldCheck,
  SpellCheck,
  Tag,
  TrendingUp,
  XCircle,
  Zap,
} from "lucide-react";

import type { EventType } from "@/types/events";

export type EventTone =
  | "info"
  | "success"
  | "warn"
  | "danger"
  | "neutral"
  | "judge"
  | "decision";

export interface EventVisual {
  Icon: LucideIcon;
  tone: EventTone;
}

/**
 * Exhaustive map: every `EventType` MUST have an entry. The unit test
 * verifies this against the real `EventType` union.
 */
export const EVENT_VISUALS: Record<EventType, EventVisual> = {
  QuestionAsked:          { Icon: MessageSquare,        tone: "info" },
  QuestionNormalized:     { Icon: SpellCheck,           tone: "info" },
  QuestionClassified:     { Icon: Tag,                  tone: "info" },
  PlanCreated:            { Icon: Compass,              tone: "decision" },
  PlanCritiqued:          { Icon: FileWarning,          tone: "warn" },
  PlanRevised:            { Icon: FilePen,              tone: "info" },
  HypothesesGenerated:    { Icon: Lightbulb,            tone: "info" },
  ToolCalled:             { Icon: Search,               tone: "info" },
  EvidenceAdded:          { Icon: FileText,             tone: "neutral" },
  ClaimCovered:           { Icon: CheckCircle2,         tone: "success" },
  ClaimUncoverable:       { Icon: MinusCircle,          tone: "warn" },
  SourceFailed:           { Icon: XCircle,              tone: "danger" },
  AmbiguityDetected:      { Icon: HelpCircle,           tone: "warn" },
  ContradictionDetected:  { Icon: AlertTriangle,        tone: "warn" },
  ContradictionResolved:  { Icon: ShieldCheck,          tone: "success" },
  UserContextChallenged:  { Icon: MessageSquareWarning, tone: "warn" },
  JudgeRuled:             { Icon: Gavel,                tone: "judge" },
  ConfidenceMismatch:     { Icon: AlertCircle,          tone: "warn" },
  AgentErrored:           { Icon: AlertOctagon,         tone: "danger" },
  ResumedAfterError:      { Icon: RotateCw,             tone: "info" },
  ResumedAfterCancel:     { Icon: RotateCw,             tone: "info" },
  Stopped:                { Icon: Flag,                 tone: "neutral" },
  SaturationDetected:     { Icon: MinusCircle,          tone: "neutral" },
  JudgeProviderDegraded:  { Icon: AlertCircle,          tone: "warn" },
  PriorRunHintReplayed:   { Icon: Recycle,              tone: "info" },
  DeepFetchPerformed:     { Icon: Download,             tone: "info" },
  QueryReformulated:      { Icon: RefreshCw,            tone: "info" },
  EchoChamberDetected:    { Icon: Repeat,               tone: "warn" },
  RouteSelected:          { Icon: GitBranch,            tone: "decision" },
  PlanGapsDetected:       { Icon: Search,               tone: "warn" },
  NoProgressDetected:     { Icon: MinusCircle,          tone: "warn" },
  LaneEscalated:          { Icon: TrendingUp,           tone: "info" },
  AgentThought:           { Icon: Brain,                tone: "info" },
  AgentAction:            { Icon: Zap,                  tone: "info" },
  AgentObservation:                 { Icon: Eye,                  tone: "neutral" },
  HypothesisEvaluated:              { Icon: ClipboardCheck,       tone: "judge" },
  HistorySummarized:                { Icon: BookText,             tone: "neutral" },
  VerificationQuestionsGenerated:   { Icon: ShieldCheck,          tone: "info" },
  CoveContradictionDetected:        { Icon: AlertOctagon,         tone: "warn" },
  DraftSynthesized:                 { Icon: FilePen,              tone: "info" },
};

const FALLBACK_VISUAL: EventVisual = { Icon: Flag, tone: "neutral" };

/**
 * Lookup with a safe fallback. Useful for synthetic frames such as the
 * `cancelled` SSE event whose type is not in the Pydantic-generated union.
 */
export function getEventVisual(type: string): EventVisual {
  return (EVENT_VISUALS as Record<string, EventVisual | undefined>)[type] ??
    FALLBACK_VISUAL;
}

/**
 * CSS custom property reference per tone. Components apply it via
 * inline `style` or `text-[var(--...)]` so colors stay token-driven.
 */
export const TONE_COLOR: Record<EventTone, string> = {
  info:     "var(--accent)",
  success:  "var(--semantic-success)",
  warn:     "var(--semantic-warning)",
  danger:   "var(--semantic-danger)",
  neutral:  "var(--semantic-neutral)",
  judge:    "var(--accent)",
  decision: "var(--accent)",
};

/**
 * `JudgeRuled` is the trust-bearing event; the prototype says it must
 * render expanded by default (ui-prototype.md §3.3). Decision events
 * (PlanCreated, JudgeRuled, ContradictionDetected, AmbiguityDetected,
 * Stopped) reserve a `forkSlot` on `EventNode` — the button itself is
 * BRD-15.
 */
export const EXPANDED_BY_DEFAULT: ReadonlySet<EventType> = new Set<EventType>([
  "JudgeRuled",
]);

export const DECISION_EVENTS: ReadonlySet<EventType> = new Set<EventType>([
  "PlanCreated",
  "JudgeRuled",
  "ContradictionDetected",
  "AmbiguityDetected",
  "Stopped",
]);

export function isDecisionEvent(type: string): boolean {
  return DECISION_EVENTS.has(type as EventType);
}
