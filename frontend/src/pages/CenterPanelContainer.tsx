/**
 * CenterPanelContainer — page-level data owner for the center panel (IP-13).
 *
 * Mounts `useRun` and renders the geometry `templates/CenterPanel` with
 * `ActionBar` in the header slot and `CenterPanelView` in the body.
 *
 * Per `eslint.config.js`, only `pages/` may import `useRun*`.
 */

import { useParams } from "react-router-dom";

import { Spinner } from "@/components/atoms";
import {
  ActionBar,
  CenterPanelView,
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
    error,
    cancel,
    isCancelling,
  } = useRun(runId);

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
          onCancel={cancel}
          isCancelling={isCancelling}
        />
      }
      body={<CenterPanelView run={run} status={status} />}
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
