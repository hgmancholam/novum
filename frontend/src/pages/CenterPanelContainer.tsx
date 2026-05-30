/**
 * CenterPanelContainer — page-level data owner for the center panel (IP-13).
 *
 * Mounts `useRun` + `useRunStream` and renders the geometry
 * `templates/CenterPanel` with `ActionBar` in the header slot and
 * `CenterPanelView` in the body. Also owns the `ForkModal` open/close
 * state for IP-15.
 *
 * Per `eslint.config.js`, only `pages/` may import `useRun*`.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Spinner } from "@/components/atoms";
import {
  ActionBar,
  CenterPanelView,
  ForkModal,
  NotFoundCard,
  RateLimitModal,
  StopReasonCard,
  type ForkModalEvent,
  type SourceEntry,
} from "@/components/organisms";
import { CenterPanel } from "@/components/templates";
import { useRun } from "@/hooks/useRun";
import { useCreateRun } from "@/hooks/useCreateRun";
import { useRunStream } from "@/hooks/useRunStream";
import { FORKABLE_EVENTS, type AnswerKind, type EventType, type StructuredAnswerData, type RunStreamEvent } from "@/types/events";

const FORKABLE_SET: ReadonlySet<string> = new Set<string>(FORKABLE_EVENTS);
const RESUME_EVENT_TYPES: ReadonlySet<EventType> = new Set<EventType>([
  "ResumedAfterError",
  "ResumedAfterCancel",
]);

function toForkModalEvent(e: RunStreamEvent): ForkModalEvent | null {
  const id = (e as { id?: unknown }).id;
  const stepIndex = e.step_index;
  if (typeof id !== "string" || typeof stepIndex !== "number") {
    return null;
  }
  return { id, type: e.type, stepIndex };
}

export function CenterPanelContainer() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const {
    run,
    status,
    isLoading,
    isError,
    isNotFound,
    error,
    cancel,
    isCancelling,
    resume,
    isResuming,
    resumeError,
    fork,
    isForking,
    forkError,
    forkedRun,
  } = useRun(runId);

  const { events } = useRunStream({
    runId,
  });

  const { create: createRunMutation, isPending: isRestarting } = useCreateRun();

  const [isForkModalOpen, setIsForkModalOpen] = useState(false);
  const [pendingForkEventId, setPendingForkEventId] = useState<string | null>(
    null
  );
  const [rateLimitModalDismissedFor, setRateLimitModalDismissedFor] = useState<
    string | null
  >(null);
  const navigatedToForkRef = useRef<string | null>(null);

  const forkableEvents = useMemo<ForkModalEvent[]>(() => {
    const out: ForkModalEvent[] = [];
    for (const e of events) {
      if (!FORKABLE_SET.has(e.type)) {
        continue;
      }
      const mapped = toForkModalEvent(e);
      if (mapped !== null) {
        out.push(mapped);
      }
    }
    return out;
  }, [events]);

  // IP-15 §9: track the latest ResumedAfter* step index so we can suppress
  // the misleading `ResearchingBanner` until the agent eventually emits a
  // new event past that point.
  const resumeStepIndex = useMemo<number | null>(() => {
    let latest: number | null = null;
    for (const e of events) {
      if (
        RESUME_EVENT_TYPES.has(e.type as EventType) &&
        typeof e.step_index === "number" &&
        (latest === null || e.step_index > latest)
      ) {
        latest = e.step_index;
      }
    }
    return latest;
  }, [events]);

  const agentEmittedAfterResume = useMemo<boolean>(() => {
    if (resumeStepIndex === null) {
      return false;
    }
    return events.some(
      (e) =>
        typeof e.step_index === "number" &&
        e.step_index > resumeStepIndex &&
        !RESUME_EVENT_TYPES.has(e.type as EventType)
    );
  }, [events, resumeStepIndex]);

  const showPostResumeNotice =
    resumeStepIndex !== null && !agentEmittedAfterResume;

  // When the LLM pool / provider quota is exhausted (GitHub pool sweep with
  // 429, or a non-github provider returns insufficient_quota / RESOURCE_EXHAUSTED),
  // the agent emits AgentErrored with error_code in {"llm_pool_rate_limited",
  // "llm_provider_quota_exhausted"}. We surface a dedicated modal so the user
  // knows the failure is a provider quota issue, not a bug. Dismissal is
  // tracked per runId so the modal does not re-open on the same run after
  // the user closes it.
  const rateLimitedRunId = useMemo<string | null>(() => {
    for (const e of events) {
      if (e.type === "AgentErrored") {
        const code = (e as { error_code?: unknown }).error_code;
        if (
          code === "llm_pool_rate_limited" ||
          code === "llm_provider_quota_exhausted"
        ) {
          return runId ?? null;
        }
      }
    }
    return null;
  }, [events, runId]);

  const isRateLimitModalOpen =
    rateLimitedRunId !== null &&
    rateLimitedRunId !== rateLimitModalDismissedFor;

  // BRD-16: extract both rendered formats from the terminal Stopped event
  const answerProse = useMemo<string | null>(() => {
    for (const e of events) {
      if (e.type === "Stopped" && typeof e.answer_prose === "string") {
        // Strip the inline sources section appended by ProseRenderer
        // (the dedicated SourcesCard replaces it with a styled card).
        const prose: string = e.answer_prose;
        const separator = "\n\n---\n\n### 📚 Sources\n\n";
        const cutIdx = prose.indexOf(separator);
        return cutIdx === -1 ? prose : prose.slice(0, cutIdx);
      }
    }
    return null;
  }, [events]);

  const answerStructured = useMemo<string | null>(() => {
    for (const e of events) {
      const structured = e["answer_structured"];
      if (e.type === "Stopped" && typeof structured === "string") {
        // Strip Confidence + Sources sections appended by StructuredRenderer
        // (they are shown via TrustSummary and SourcesCard respectively).
        const separator = "\n\n---\n\n### 📊 Confidence\n\n";
        const cutIdx = structured.indexOf(separator);
        return cutIdx === -1 ? structured : structured.slice(0, cutIdx);
      }
    }
    return null;
  }, [events]);

  // RF-10: typed structured payload from the backend; FE renders blocks natively.
  const answerStructuredData = useMemo<StructuredAnswerData | null>(() => {
    for (const e of events) {
      if (e.type !== "Stopped") {
        continue;
      }
      const raw = (e as Record<string, unknown>)["answer_structured_data"];
      if (raw === null || raw === undefined || typeof raw !== "object") {
        continue;
      }
      const obj = raw as { summary?: unknown; blocks?: unknown };
      if (typeof obj.summary !== "string" || !Array.isArray(obj.blocks)) {
        continue;
      }
      return obj as unknown as StructuredAnswerData;
    }
    return null;
  }, [events]);

  // RF-17 / C3 fallback: terminal Stopped event carries the AnswerKind that
  // shaped the synthesizer prompt. We surface it as a badge so the user can
  // tell a judge-confirmed answer from a best-effort fallback.
  const answerKind = useMemo<AnswerKind | null>(() => {
    for (const e of events) {
      if (e.type !== "Stopped") {
        continue;
      }
      const raw = (e as Record<string, unknown>)["answer_kind"];
      if (
        raw === "direct" ||
        raw === "weighted" ||
        raw === "scenario" ||
        raw === "tradeoff" ||
        raw === "ethical_redirect" ||
        raw === "best_effort"
      ) {
        return raw;
      }
    }
    return null;
  }, [events]);

  /**
   * Confidence metrics from the last JudgeRuled event (RF-12).
   * final_confidence = min(structural, judge).
   */
  const judgeConfidence = useMemo<{
    finalConfidence: number;
    structuralConfidence: number;
    judgeConfidence: number;
    passed: boolean;
  } | null>(() => {
    let latest: {
      finalConfidence: number;
      structuralConfidence: number;
      judgeConfidence: number;
      passed: boolean;
    } | null = null;
    for (const e of events) {
      if (
        e.type === "JudgeRuled" &&
        typeof e.final_confidence === "number" &&
        typeof e.structural_confidence === "number" &&
        typeof e.judge_confidence === "number" &&
        typeof e.passed === "boolean"
      ) {
        latest = {
          finalConfidence: e.final_confidence,
          structuralConfidence: e.structural_confidence,
          judgeConfidence: e.judge_confidence,
          passed: e.passed,
        };
      }
    }
    return latest;
  }, [events]);

  /**
   * PR-1 Mejora 2.2 — Structural-confidence fallback from `Stopped.stop_rationale`.
   * Used to render an honest "structural N% · judge not confirmed" badge instead
   * of treating a null judge confidence as 0 %.
   */
  const structuralFallback = useMemo<{
    confidence: number;
    kind: "structural";
  } | null>(() => {
    if (judgeConfidence !== null) {
      return null;
    }
    for (let i = events.length - 1; i >= 0; i -= 1) {
      const e = events[i];
      if (e === undefined || e.type !== "Stopped") {
        continue;
      }
      const rationale = (e as Record<string, unknown>)["stop_rationale"] as
        | Record<string, unknown>
        | null
        | undefined;
      if (rationale === null || rationale === undefined) {
        continue;
      }
      const kind = rationale["confidence_kind"];
      const confidence = rationale["confidence"];
      if (kind === "structural" && typeof confidence === "number") {
        return { confidence, kind: "structural" };
      }
    }
    return null;
  }, [events, judgeConfidence]);

  /**
   * Natural-language stop rationale from the latest Stopped event
   * (`triggering_signal` + `summary`). Surfaced in TrustSummary so the user
   * can tell apart "budget", "no_progress" and "wall_clock" inside the same
   * `stopped_by_budget` enum value.
   */
  const stopRationale = useMemo<{
    triggeringSignal: string;
    summary: string;
  } | null>(() => {
    for (let i = events.length - 1; i >= 0; i -= 1) {
      const e = events[i];
      if (e === undefined || e.type !== "Stopped") {
        continue;
      }
      const rationale = (e as Record<string, unknown>)["stop_rationale"] as
        | Record<string, unknown>
        | null
        | undefined;
      if (rationale === null || rationale === undefined) {
        continue;
      }
      const signal = rationale["triggering_signal"];
      const summary = rationale["summary"];
      if (typeof signal === "string" && typeof summary === "string") {
        return { triggeringSignal: signal, summary };
      }
    }
    return null;
  }, [events]);

  /**
   * Deduplicated source list from EvidenceAdded events.
   * Each URL appears at most once; when duplicated the highest confidence wins.
   */
  const sources = useMemo<SourceEntry[]>(() => {
    const byUrl = new Map<string, SourceEntry>();
    for (const e of events) {
      if (e.type !== "EvidenceAdded") {
        continue;
      }
      const url = typeof e.source_url === "string" ? e.source_url : "";
      const title =
        typeof e.source_title === "string" ? e.source_title : url;
      const sourceType =
        e.source_type === "wikipedia" ? "wikipedia" : ("tavily" as const);
      const polarity =
        e.polarity === "contradicts"
          ? "contradicts"
          : e.polarity === "supports"
            ? "supports"
            : ("neutral" as const);
      const confidence =
        typeof e.confidence === "number" ? e.confidence : 0;
      const authorityTier =
        e.authority_tier === "primary_authoritative" ||
        e.authority_tier === "reputable_secondary" ||
        e.authority_tier === "general" ||
        e.authority_tier === "low_signal"
          ? e.authority_tier
          : null;

      const existing = byUrl.get(url);
      if (existing === undefined || confidence > existing.confidence) {
        byUrl.set(url, { url, title, sourceType, polarity, confidence, authorityTier });
      }
    }
    return [...byUrl.values()];
  }, [events]);

  // Client-side view format — defaults to "structured" (the only format the
  // form submits as of D-COPY-AND-FORMAT-INLINE); toggleable post-answer
  // via AnswerToolbar inside the answer card.
  const [viewFormat, setViewFormat] = useState<string>(
    run?.outputFormat ?? "structured"
  );

  useEffect(() => {
    if (forkedRun === undefined) {
      return;
    }
    if (navigatedToForkRef.current === forkedRun.id) {
      return;
    }
    navigatedToForkRef.current = forkedRun.id;
    setIsForkModalOpen(false);
    setPendingForkEventId(null);
    void navigate(`/runs/${forkedRun.id}`);
  }, [forkedRun, navigate]);

  const handleForkSelect = (eventId: string): void => {
    setPendingForkEventId(eventId);
    fork(eventId);
  };

  const handleForkClose = (): void => {
    setIsForkModalOpen(false);
    setPendingForkEventId(null);
  };

  const handleRestart = async (): Promise<void> => {
    if (run === undefined) {
      return;
    }
    const created = await createRunMutation({
      question: run.question,
      user_context: run.userContext,
      output_format: run.outputFormat,
      confidence_threshold: run.confidenceThreshold,
    });
    void navigate(`/runs/${created.id}`);
  };

  if (isNotFound) {
    return <CenterPanel body={<NotFoundCard runId={runId} />} />;
  }

  // C1 — initial loading
  if (isLoading || run === undefined || status === undefined) {
    if (isError) {
      return renderError(error);
    }
    return (
      <CenterPanel
        header={
          <ActionBar
            status={undefined}
            onCancel={cancel}
            isCancelling={isCancelling}
          />
        }
        body={
          <div
            data-testid="center-loading"
            className="flex h-full items-center justify-center"
          >
            <Spinner size="lg" label="Loading run" />
          </div>
        }
      />
    );
  }

  if (isError) {
    return renderError(error);
  }

  return (
    <>
      <CenterPanel
        header={
          <ActionBar
            status={status}
            stopReason={run.stopReason}
            onCancel={cancel}
            isCancelling={isCancelling}
            onResume={resume}
            isResuming={isResuming}
            onFork={() => {
              setIsForkModalOpen(true);
            }}
            isForking={isForking}
            forkableEventCount={forkableEvents.length}
            onRestart={() => {
              void handleRestart();
            }}
            isRestarting={isRestarting}
            showPostResumeNotice={showPostResumeNotice}
          />
        }
        body={
          <div className="flex flex-col gap-2">
            <CenterPanelView
              run={run}
              status={status}
              events={events}
              answerProse={answerProse}
              answerStructured={answerStructured}
              answerStructuredData={answerStructuredData}
              answerKind={answerKind}
              viewFormat={viewFormat}
              onViewFormatChange={setViewFormat}
              sources={sources}
              judgeConfidence={judgeConfidence}
              structuralFallback={structuralFallback}
              stopRationale={stopRationale}
              showPostResumeNotice={showPostResumeNotice}
              onResume={resume}
              isResuming={isResuming}
            />
            {resumeError !== null ? (
              <p
                role="alert"
                data-testid="resume-error"
                className="mx-auto w-full max-w-3xl text-sm text-(--semantic-danger)"
              >
                Could not resume: {resumeError.message}
              </p>
            ) : null}
          </div>
        }
      />
      <ForkModal
        isOpen={isForkModalOpen}
        events={forkableEvents}
        onSelect={handleForkSelect}
        onClose={handleForkClose}
        isForking={isForking}
        pendingEventId={pendingForkEventId}
        error={forkError}
      />
      <RateLimitModal
        isOpen={isRateLimitModalOpen}
        onClose={() => {
          setRateLimitModalDismissedFor(rateLimitedRunId);
        }}
      />
    </>
  );
}

function renderError(error: Error | null) {
  const message = error?.message ?? "Failed to load this run.";
  return (
    <CenterPanel
      body={
        <div
          data-testid="center-error"
          className="mx-auto mt-10 w-full max-w-3xl"
        >
          <StopReasonCard reason="errored" explanation={message} />
        </div>
      }
    />
  );
}
