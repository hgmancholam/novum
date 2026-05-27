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
  StopReasonCard,
  type ForkModalEvent,
} from "@/components/organisms";
import { CenterPanel } from "@/components/templates";
import { useRun } from "@/hooks/useRun";
import { useRunStream, type RunStreamEvent } from "@/hooks/useRunStream";
import { FORKABLE_EVENTS, type EventType } from "@/types/events";

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

  const { events } = useRunStream({ runId });

  const [isForkModalOpen, setIsForkModalOpen] = useState(false);
  const [pendingForkEventId, setPendingForkEventId] = useState<string | null>(
    null
  );
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
            showPostResumeNotice={showPostResumeNotice}
          />
        }
        body={
          <div className="flex flex-col gap-2">
            <CenterPanelView
              run={run}
              status={status}
              suppressResearchingBanner={showPostResumeNotice}
              latestEvent={events.at(-1)}
              eventCount={events.length}
            />
            {resumeError !== null ? (
              <p
                role="alert"
                data-testid="resume-error"
                className="mx-auto w-full max-w-3xl text-sm text-[var(--semantic-danger)]"
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
