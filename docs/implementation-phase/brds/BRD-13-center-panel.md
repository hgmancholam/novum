# BRD-13: Center Panel (Question & Answer)

**Document ID:** BRD-13
**Version:** 1.0
**Status:** Draft
**Author:** BSA Agent
**Date:** 2026-05-26
**Implementation Order:** 14 of 19

---

## 1. Executive Summary

Implement the Center Panel displaying the current question, streaming answer, confidence visualization, and action buttons (cancel, fork). Covers states C1-C13 from the UI prototype.

## 2. RF Traceability

| RF | Requirement | Coverage |
|----|-------------|----------|
| RF-08 | Live cancellation (red button) | Complete |
| RF-12 | Confidence visualization | Complete |
| RF-13 | Trust guarantees display | Complete |

## 3. Dependencies

| Depends On | Required For |
|------------|--------------|
| BRD-02, BRD-10, BRD-11 | BRD-15, BRD-16 |

---

## 4. Technical Specification

### 4.1 File Structure

```
frontend/
  src/
    components/
      organisms/
        CenterPanel.tsx
        QuestionDisplay.tsx
        AnswerDisplay.tsx
        ConfidenceCard.tsx
        ActionBar.tsx
        StopReasonCard.tsx
    hooks/
      useRun.ts
```

### 4.2 States from UI Prototype

| State | Description | Implementation |
|-------|-------------|----------------|
| C1 | Initial loading | Skeleton + spinner |
| C2 | Question displayed | Question card |
| C3 | Researching | Progress indicator |
| C4 | Evidence gathering | Source list updating |
| C5 | Judging | Judge evaluation in progress |
| C6 | Answer streaming | Prose/structured rendering |
| C7 | Completed (confirmed) | Green confidence badge |
| C8 | Completed (honest stop) | Yellow/orange badge + explanation |
| C9 | Error state | Red error card |
| C10 | Cancelled | Grey cancelled badge |
| C11 | Fork point selection | Highlight forkable events |
| C12 | Low confidence warning | Yellow warning banner |
| C13 | Mismatch alert | Trust flag display |

### 4.3 Run Hook

#### frontend/src/hooks/useRun.ts

```typescript
/**
 * Hook for fetching run details and streaming events.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useEffect, useCallback } from "react";
import { getRun, cancelRun, forkRun } from "@/lib/api";
import { useRunStream } from "./useRunStream";
import type { RunEvent } from "@/types/events";

export function useRun(runId: string) {
  const queryClient = useQueryClient();
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [latestAnswer, setLatestAnswer] = useState<string | null>(null);
  const [confidence, setConfidence] = useState<number | null>(null);
  const [stopReason, setStopReason] = useState<string | null>(null);

  // Fetch initial run data
  const runQuery = useQuery({
    queryKey: ["run", runId],
    queryFn: () => getRun(runId),
  });

  // Handle streaming events
  const handleEvent = useCallback((event: RunEvent) => {
    setEvents((prev) => [...prev, event]);

    // Update state based on event type
    switch (event.type) {
      case "AnswerDrafted":
        setLatestAnswer((event as any).content);
        break;
      case "ConfidenceCalculated":
        setConfidence((event as any).final);
        break;
      case "Stopped":
        setStopReason((event as any).reason);
        queryClient.invalidateQueries({ queryKey: ["run", runId] });
        break;
    }
  }, [queryClient, runId]);

  const {
    isConnected,
    isComplete,
    error: streamError,
    reconnect,
  } = useRunStream({
    runId,
    enabled: runQuery.data?.status === "running",
    onEvent: handleEvent,
  });

  // Cancel mutation
  const cancelMutation = useMutation({
    mutationFn: () => cancelRun(runId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["run", runId] });
    },
  });

  // Fork mutation
  const forkMutation = useMutation({
    mutationFn: (stepIndex: number) => forkRun(runId, stepIndex),
    onSuccess: (newRun) => {
      queryClient.invalidateQueries({ queryKey: ["runs"] });
      return newRun;
    },
  });

  return {
    run: runQuery.data,
    isLoading: runQuery.isLoading,
    isError: runQuery.isError || !!streamError,
    error: runQuery.error || streamError,
    events,
    latestAnswer,
    confidence,
    stopReason,
    isConnected,
    isComplete,
    reconnect,
    cancel: cancelMutation.mutate,
    isCancelling: cancelMutation.isPending,
    fork: forkMutation.mutateAsync,
    isForking: forkMutation.isPending,
  };
}
```

### 4.4 Center Panel Component

#### frontend/src/components/organisms/CenterPanel.tsx

```typescript
/**
 * Center Panel - Question & Answer display (RF-13)
 */

import { useParams } from "react-router-dom";
import { Spinner } from "@/components/atoms";
import { QuestionDisplay } from "./QuestionDisplay";
import { AnswerDisplay } from "./AnswerDisplay";
import { ConfidenceCard } from "./ConfidenceCard";
import { ActionBar } from "./ActionBar";
import { StopReasonCard } from "./StopReasonCard";
import { useRun } from "@/hooks/useRun";

export function CenterPanel() {
  const { runId } = useParams<{ runId: string }>();

  if (!runId) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-gray-500">Select a research run</p>
      </div>
    );
  }

  return <CenterPanelContent runId={runId} />;
}

function CenterPanelContent({ runId }: { runId: string }) {
  const {
    run,
    isLoading,
    isError,
    error,
    events,
    latestAnswer,
    confidence,
    stopReason,
    isConnected,
    isComplete,
    cancel,
    isCancelling,
    fork,
    isForking,
  } = useRun(runId);

  // C1 - Initial loading
  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  // C9 - Error state
  if (isError || !run) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 p-8">
        <div className="rounded-lg bg-red-50 p-6 text-center">
          <h3 className="mb-2 text-lg font-semibold text-red-800">
            Error Loading Run
          </h3>
          <p className="text-red-600">
            {error instanceof Error ? error.message : "Unknown error"}
          </p>
        </div>
      </div>
    );
  }

  const isRunning = run.status === "running";
  const showCancel = isRunning && isConnected;

  return (
    <div className="flex h-full flex-col">
      {/* Header with actions */}
      <ActionBar
        isRunning={isRunning}
        showCancel={showCancel}
        onCancel={cancel}
        isCancelling={isCancelling}
        onFork={(stepIndex) => fork(stepIndex)}
        isForking={isForking}
        events={events}
      />

      {/* Main content */}
      <div className="flex-1 overflow-y-auto p-6">
        {/* C2 - Question display */}
        <QuestionDisplay question={run.question} />

        {/* C3, C4, C5 - Progress indicators */}
        {isRunning && (
          <div className="my-6">
            <ResearchProgress events={events} />
          </div>
        )}

        {/* C6 - Answer streaming / C7, C8 - Completed answer */}
        {latestAnswer && (
          <AnswerDisplay
            content={latestAnswer}
            isStreaming={isRunning}
            format={run.outputFormat}
          />
        )}

        {/* C7, C8, C10 - Stop reason card */}
        {stopReason && (
          <StopReasonCard reason={stopReason} events={events} />
        )}

        {/* C12, C13 - Confidence with warnings */}
        {confidence !== null && (
          <ConfidenceCard
            confidence={confidence}
            threshold={run.threshold}
            events={events}
          />
        )}
      </div>
    </div>
  );
}

function ResearchProgress({ events }: { events: any[] }) {
  // Determine current phase from events
  const lastEvent = events.at(-1);
  const phase = lastEvent?.type || "Initializing";

  const phases = [
    "Initializing",
    "Planning",
    "Searching",
    "Analyzing",
    "Judging",
    "Finalizing",
  ];

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-sm font-medium text-gray-700">Research in Progress</span>
        <Spinner size="sm" />
      </div>
      <div className="flex gap-1">
        {phases.map((p, i) => (
          <div
            key={p}
            className={`h-1 flex-1 rounded-full ${
              i <= phases.indexOf(phase) ? "bg-blue-500" : "bg-gray-200"
            }`}
          />
        ))}
      </div>
      <p className="mt-2 text-xs text-gray-500">{phase}...</p>
    </div>
  );
}
```

### 4.5 Question Display Component

#### frontend/src/components/organisms/QuestionDisplay.tsx

```typescript
/**
 * Question display card.
 */

interface QuestionDisplayProps {
  question: string;
}

export function QuestionDisplay({ question }: QuestionDisplayProps) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6">
      <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-gray-500">
        Research Question
      </h2>
      <p className="text-xl font-semibold text-gray-900">{question}</p>
    </div>
  );
}
```

### 4.6 Answer Display Component

#### frontend/src/components/organisms/AnswerDisplay.tsx

```typescript
/**
 * Answer display with markdown rendering.
 */

import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import { cn } from "@/lib/cn";

interface AnswerDisplayProps {
  content: string;
  isStreaming: boolean;
  format?: "prose" | "structured";
}

export function AnswerDisplay({
  content,
  isStreaming,
  format = "prose",
}: AnswerDisplayProps) {
  return (
    <div className="mt-6 rounded-lg border border-gray-200 bg-white p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-medium uppercase tracking-wide text-gray-500">
          Answer
        </h2>
        {isStreaming && (
          <span className="flex items-center gap-2 text-sm text-blue-600">
            <span className="h-2 w-2 animate-pulse rounded-full bg-blue-600" />
            Streaming
          </span>
        )}
      </div>

      <div
        className={cn(
          "prose prose-gray max-w-none",
          isStreaming && "animate-pulse-subtle"
        )}
      >
        <ReactMarkdown
          components={{
            code({ node, className, children, ...props }) {
              const match = /language-(\w+)/.exec(className || "");
              const inline = !match;

              if (inline) {
                return (
                  <code className="rounded bg-gray-100 px-1 py-0.5" {...props}>
                    {children}
                  </code>
                );
              }

              return (
                <SyntaxHighlighter
                  style={oneLight}
                  language={match[1]}
                  PreTag="div"
                >
                  {String(children).replace(/\n$/, "")}
                </SyntaxHighlighter>
              );
            },
          }}
        >
          {content}
        </ReactMarkdown>
      </div>
    </div>
  );
}
```

### 4.7 Confidence Card Component

#### frontend/src/components/organisms/ConfidenceCard.tsx

```typescript
/**
 * Confidence visualization card (RF-12, RF-13).
 */

import { cn } from "@/lib/cn";
import { ConfidenceBar } from "@/components/molecules";

interface ConfidenceEvent {
  type: "ConfidenceCalculated";
  structural: {
    coverage: number;
    agreement: number;
    diversity: number;
    no_conflict: number;
    score: number;
  };
  judge: number;
  final: number;
  mismatch?: {
    has_mismatch: boolean;
    trust_flag?: string;
  };
}

interface ConfidenceCardProps {
  confidence: number;
  threshold: number;
  events: any[];
}

export function ConfidenceCard({
  confidence,
  threshold,
  events,
}: ConfidenceCardProps) {
  // Find the confidence event
  const confidenceEvent = events.find(
    (e) => e.type === "ConfidenceCalculated"
  ) as ConfidenceEvent | undefined;

  const structural = confidenceEvent?.structural;
  const judge = confidenceEvent?.judge ?? confidence;
  const mismatch = confidenceEvent?.mismatch;
  const passed = confidence >= threshold;

  return (
    <div
      className={cn(
        "mt-6 rounded-lg border p-6",
        passed
          ? "border-green-200 bg-green-50"
          : "border-yellow-200 bg-yellow-50"
      )}
    >
      <h2 className="mb-4 text-sm font-medium uppercase tracking-wide text-gray-700">
        Confidence Assessment
      </h2>

      {/* Main confidence bar */}
      <ConfidenceBar value={confidence} threshold={threshold} />

      {/* Formula explanation */}
      <div className="mt-4 text-sm text-gray-600">
        <p className="font-mono">
          final_confidence = min(S, J) = min({structural?.score?.toFixed(2) ?? "?"}, {judge.toFixed(2)}) = {confidence.toFixed(2)}
        </p>
      </div>

      {/* Structural breakdown */}
      {structural && (
        <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
          <StructuralMetric label="Coverage" value={structural.coverage} />
          <StructuralMetric label="Agreement" value={structural.agreement} />
          <StructuralMetric label="Diversity" value={structural.diversity} />
          <StructuralMetric label="No Conflict" value={structural.no_conflict} />
        </div>
      )}

      {/* C13 - Mismatch alert */}
      {mismatch?.has_mismatch && mismatch.trust_flag && (
        <div className="mt-4 rounded-md border border-amber-300 bg-amber-50 p-3">
          <p className="text-sm text-amber-800">
            <strong>Trust Note:</strong> {mismatch.trust_flag}
          </p>
        </div>
      )}
    </div>
  );
}

function StructuralMetric({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <span className="text-gray-500">{label}:</span>{" "}
      <span className="font-medium">{(value * 100).toFixed(0)}%</span>
    </div>
  );
}
```

### 4.8 Stop Reason Card Component

#### frontend/src/components/organisms/StopReasonCard.tsx

```typescript
/**
 * Stop reason explanation card (RF-01, RF-04).
 */

import { cn } from "@/lib/cn";
import type { StopReason } from "@/types/events";

interface StopReasonCardProps {
  reason: StopReason;
  events: any[];
}

const reasonConfig: Record<
  StopReason,
  {
    title: string;
    description: string;
    variant: "success" | "warning" | "error" | "info";
  }
> = {
  judge_confirmed: {
    title: "Answer Confirmed",
    description: "The judge has verified this answer meets the confidence threshold.",
    variant: "success",
  },
  honest_unanswerable: {
    title: "Insufficient Evidence",
    description:
      "After thorough research, not enough reliable evidence was found to answer this question confidently.",
    variant: "warning",
  },
  honest_contradiction: {
    title: "Sources Contradict",
    description:
      "Multiple sources provide conflicting information that cannot be reconciled.",
    variant: "warning",
  },
  honest_ambiguous: {
    title: "Question Ambiguous",
    description:
      "The question has multiple valid interpretations. Please clarify what you're asking.",
    variant: "warning",
  },
  stopped_by_budget: {
    title: "Research Limit Reached",
    description:
      "Maximum research iterations reached. The current answer represents best available evidence.",
    variant: "info",
  },
  user_cancelled: {
    title: "Cancelled by User",
    description: "Research was stopped by user request.",
    variant: "info",
  },
  errored: {
    title: "Error Occurred",
    description: "An unexpected error prevented completion.",
    variant: "error",
  },
};

const variantStyles = {
  success: "border-green-200 bg-green-50 text-green-800",
  warning: "border-yellow-200 bg-yellow-50 text-yellow-800",
  error: "border-red-200 bg-red-50 text-red-800",
  info: "border-gray-200 bg-gray-50 text-gray-800",
};

export function StopReasonCard({ reason, events }: StopReasonCardProps) {
  const config = reasonConfig[reason];

  // Find the Stopped event for additional context
  const stoppedEvent = events.find((e) => e.type === "Stopped");

  return (
    <div className={cn("mt-6 rounded-lg border p-6", variantStyles[config.variant])}>
      <h3 className="mb-2 text-lg font-semibold">{config.title}</h3>
      <p className="text-sm">{config.description}</p>

      {/* Additional context from the event */}
      {stoppedEvent?.explanation && (
        <p className="mt-3 text-sm opacity-80">{stoppedEvent.explanation}</p>
      )}
    </div>
  );
}
```

### 4.9 Action Bar Component

#### frontend/src/components/organisms/ActionBar.tsx

```typescript
/**
 * Action bar with cancel/fork buttons (RF-08).
 */

import { Button } from "@/components/atoms";

interface ActionBarProps {
  isRunning: boolean;
  showCancel: boolean;
  onCancel: () => void;
  isCancelling: boolean;
  onFork: (stepIndex: number) => Promise<any>;
  isForking: boolean;
  events: any[];
}

export function ActionBar({
  isRunning,
  showCancel,
  onCancel,
  isCancelling,
  onFork,
  isForking,
  events,
}: ActionBarProps) {
  // Find forkable events
  const forkableEvents = events.filter((e) =>
    [
      "PlanCreated",
      "EvidenceCollected",
      "ContradictionDetected",
      "AnswerDrafted",
      "JudgeVerdict",
    ].includes(e.type)
  );

  return (
    <div className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-3">
      <div className="flex items-center gap-2">
        {isRunning && (
          <span className="flex items-center gap-2 text-sm text-green-600">
            <span className="h-2 w-2 animate-pulse rounded-full bg-green-500" />
            Live
          </span>
        )}
      </div>

      <div className="flex items-center gap-2">
        {/* Cancel button - RF-08 */}
        {showCancel && (
          <Button
            variant="danger"
            size="sm"
            onClick={onCancel}
            loading={isCancelling}
          >
            Cancel
          </Button>
        )}

        {/* Fork button - only when not running */}
        {!isRunning && forkableEvents.length > 0 && (
          <ForkDropdown
            events={forkableEvents}
            onFork={onFork}
            isForking={isForking}
          />
        )}
      </div>
    </div>
  );
}

function ForkDropdown({
  events,
  onFork,
  isForking,
}: {
  events: any[];
  onFork: (stepIndex: number) => Promise<any>;
  isForking: boolean;
}) {
  // Simple dropdown - could use Radix DropdownMenu
  return (
    <div className="relative">
      <Button variant="secondary" size="sm" disabled={isForking}>
        {isForking ? "Forking..." : "Fork from..."}
      </Button>
      {/* Dropdown implementation deferred to BRD-15 */}
    </div>
  );
}
```

---

## 5. Acceptance Criteria

### AC-01: Question Displays Correctly (C2)
```gherkin
Given a run with question "What is TypeScript?"
When I view the center panel
Then I see "Research Question" header
  And the question text displayed prominently
```

### AC-02: Answer Streams Live (C6)
```gherkin
Given a running research
When the agent emits AnswerDrafted events
Then the answer updates in real-time
  And a "Streaming" indicator is visible
```

### AC-03: Cancel Button Stops Research (RF-08)
```gherkin
Given a running research
When I click the Cancel button
Then a Stopped event with reason=user_cancelled is emitted
  And the streaming stops
```

### AC-04: Confidence Shows min(S,J) Formula (RF-12)
```gherkin
Given a completed run with S=0.8 and J=0.7
When I view the confidence card
Then I see "final_confidence = min(S, J) = min(0.80, 0.70) = 0.70"
  And the structural breakdown is visible
```

---

## 6. Implementation Checklist

- [ ] Create `frontend/src/hooks/useRun.ts`
- [ ] Create `frontend/src/components/organisms/CenterPanel.tsx`
- [ ] Create `frontend/src/components/organisms/QuestionDisplay.tsx`
- [ ] Create `frontend/src/components/organisms/AnswerDisplay.tsx`
- [ ] Create `frontend/src/components/organisms/ConfidenceCard.tsx`
- [ ] Create `frontend/src/components/organisms/StopReasonCard.tsx`
- [ ] Create `frontend/src/components/organisms/ActionBar.tsx`
- [ ] Update `ResearchPage` to use real `CenterPanel`
- [ ] Write component tests
- [ ] Test streaming behavior

## 7. Testing Strategy

| Test Type | Tool | Target | Coverage |
|-----------|------|--------|----------|
| Unit | Vitest + RTL | Components | 100% |
| Integration | Vitest + MSW | Streaming | 100% |

## 8. Environment Variables

_None required._

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Markdown injection | High | Low | React-markdown sanitizes |
| Rapid re-renders | Med | Med | Memo + batching |

## 10. Out of Scope

- Print/export answer
- Answer versioning
- Inline editing
