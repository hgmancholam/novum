/**
 * CenterPanelContainer — page-level data owner for the center panel (IP-13).
 *
 * Mounts `useRun` and renders the geometry `templates/CenterPanel` with
 * `ActionBar` in the header slot and `CenterPanelView` in the body.
 *
 * Iter 2 adds:
 *   - 404 handling → `NotFoundCard` (C13)
 *   - Resume wiring (RF-11)
 *
 * Per `eslint.config.js`, only `pages/` may import `useRun*`.
 */

import { useParams } from "react-router-dom";

import { Spinner } from "@/components/atoms";
import {
  ActionBar,
  CenterPanelView,
  NotFoundCard,
  StopReasonCard,
} from "@/components/organisms";
import { CenterPanel } from "@/components/templates";
import { useRun } from "@/hooks/useRun";

export function CenterPanelContainer() {
  const { runId } = useParams<{ runId: string }>();
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
  } = useRun(runId);

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
    <CenterPanel
      header={
        <ActionBar
          status={status}
          stopReason={run.stopReason}
          onCancel={cancel}
          isCancelling={isCancelling}
          onResume={resume}
          isResuming={isResuming}
        />
      }
      body={
        <div className="flex flex-col gap-2">
          <CenterPanelView run={run} status={status} />
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
