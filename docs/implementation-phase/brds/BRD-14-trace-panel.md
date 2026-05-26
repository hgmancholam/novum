# BRD-14: Trace Panel (Right Sidebar)

**Document ID:** BRD-14
**Version:** 1.0
**Status:** Draft
**Author:** BSA Agent
**Date:** 2026-05-26
**Implementation Order:** 15 of 19

---

## 1. Executive Summary

Implement the Trace Panel (right sidebar) showing the full event trace for inspectability per RF-13. Covers states T1-T5 from the UI prototype including event list, details view, and diff comparison.

## 2. RF Traceability

| RF | Requirement | Coverage |
|----|-------------|----------|
| RF-13 | Full inspectability, trust guarantees | Complete |
| RF-03 | Event trace for fork point selection | Complete |

## 3. Dependencies

| Depends On | Required For |
|------------|--------------|
| BRD-02, BRD-10, BRD-11 | BRD-15 |

---

## 4. Technical Specification

### 4.1 File Structure

```
frontend/
  src/
    components/
      organisms/
        TracePanel.tsx
        TraceEventList.tsx
        TraceEventItem.tsx
        TraceEventDetails.tsx
        TraceDiffView.tsx
```

### 4.2 States from UI Prototype

| State | Description | Implementation |
|-------|-------------|----------------|
| T1 | Empty trace | "No events yet" message |
| T2 | Event list | Chronological event cards |
| T3 | Event selected | Expanded details view |
| T4 | Diff view | Compare two events |
| T5 | Loading | Skeleton loaders |

### 4.3 Event Icons and Colors

```typescript
// Event type → icon and color mapping
const EVENT_STYLES: Record<string, { icon: string; color: string }> = {
  QuestionAsked: { icon: "❓", color: "blue" },
  PlanCreated: { icon: "📋", color: "purple" },
  SearchStarted: { icon: "🔍", color: "gray" },
  SourceQueried: { icon: "🌐", color: "cyan" },
  EvidenceCollected: { icon: "📄", color: "green" },
  ContradictionDetected: { icon: "⚠️", color: "yellow" },
  AnswerDrafted: { icon: "✏️", color: "blue" },
  JudgeVerdict: { icon: "⚖️", color: "purple" },
  ConfidenceCalculated: { icon: "📊", color: "green" },
  CriticFeedback: { icon: "💬", color: "orange" },
  Stopped: { icon: "🛑", color: "red" },
  ResumeStarted: { icon: "▶️", color: "blue" },
  ForkCreated: { icon: "🍴", color: "purple" },
};
```

### 4.4 Trace Panel Component

#### frontend/src/components/organisms/TracePanel.tsx

```typescript
/**
 * Trace Panel - Event timeline (RF-13)
 * 
 * States:
 * T1 - Empty
 * T2 - List
 * T3 - Selected
 * T4 - Diff
 * T5 - Loading
 */

import { useState, useCallback } from "react";
import { Spinner, Button } from "@/components/atoms";
import { TraceEventList } from "./TraceEventList";
import { TraceEventDetails } from "./TraceEventDetails";
import { TraceDiffView } from "./TraceDiffView";
import type { RunEvent } from "@/types/events";

interface TracePanelProps {
  events: RunEvent[];
  isLoading: boolean;
  isStreaming: boolean;
}

type ViewMode = "list" | "details" | "diff";

export function TracePanel({
  events,
  isLoading,
  isStreaming,
}: TracePanelProps) {
  const [viewMode, setViewMode] = useState<ViewMode>("list");
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [diffIndices, setDiffIndices] = useState<[number, number] | null>(null);

  const handleSelectEvent = useCallback((index: number) => {
    setSelectedIndex(index);
    setViewMode("details");
  }, []);

  const handleStartDiff = useCallback(() => {
    if (selectedIndex !== null) {
      setDiffIndices([selectedIndex, selectedIndex]);
      setViewMode("diff");
    }
  }, [selectedIndex]);

  const handleSetDiffTarget = useCallback(
    (index: number) => {
      if (diffIndices) {
        setDiffIndices([diffIndices[0], index]);
      }
    },
    [diffIndices]
  );

  const handleBack = useCallback(() => {
    setViewMode("list");
    setSelectedIndex(null);
    setDiffIndices(null);
  }, []);

  // T5 - Loading
  if (isLoading) {
    return (
      <div className="flex h-full flex-col">
        <TracePanelHeader title="Trace" />
        <div className="flex flex-1 items-center justify-center">
          <Spinner size="lg" />
        </div>
      </div>
    );
  }

  // T1 - Empty
  if (events.length === 0) {
    return (
      <div className="flex h-full flex-col">
        <TracePanelHeader title="Trace" />
        <div className="flex flex-1 flex-col items-center justify-center p-4 text-center">
          <p className="text-gray-500">No events yet</p>
          <p className="mt-2 text-sm text-gray-400">
            Events will appear here as the research progresses
          </p>
        </div>
      </div>
    );
  }

  // T4 - Diff view
  if (viewMode === "diff" && diffIndices) {
    return (
      <div className="flex h-full flex-col">
        <TracePanelHeader
          title="Compare Events"
          onBack={handleBack}
          showBack
        />
        <TraceDiffView
          event1={events[diffIndices[0]]}
          event2={events[diffIndices[1]]}
          onSelectSecond={(index) => handleSetDiffTarget(index)}
          events={events}
        />
      </div>
    );
  }

  // T3 - Details view
  if (viewMode === "details" && selectedIndex !== null) {
    return (
      <div className="flex h-full flex-col">
        <TracePanelHeader
          title={`Event ${selectedIndex + 1}`}
          onBack={handleBack}
          showBack
        />
        <TraceEventDetails
          event={events[selectedIndex]}
          index={selectedIndex}
          onDiff={handleStartDiff}
        />
      </div>
    );
  }

  // T2 - List view
  return (
    <div className="flex h-full flex-col">
      <TracePanelHeader
        title="Trace"
        subtitle={`${events.length} events`}
        isStreaming={isStreaming}
      />
      <TraceEventList
        events={events}
        selectedIndex={selectedIndex}
        onSelect={handleSelectEvent}
      />
    </div>
  );
}

function TracePanelHeader({
  title,
  subtitle,
  isStreaming,
  showBack,
  onBack,
}: {
  title: string;
  subtitle?: string;
  isStreaming?: boolean;
  showBack?: boolean;
  onBack?: () => void;
}) {
  return (
    <div className="flex items-center justify-between border-b border-gray-200 p-4">
      <div className="flex items-center gap-2">
        {showBack && (
          <button
            onClick={onBack}
            className="rounded p-1 hover:bg-gray-100"
            aria-label="Back"
          >
            <svg
              className="h-5 w-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 19l-7-7 7-7"
              />
            </svg>
          </button>
        )}
        <div>
          <h2 className="text-lg font-semibold">{title}</h2>
          {subtitle && (
            <p className="text-sm text-gray-500">{subtitle}</p>
          )}
        </div>
      </div>
      {isStreaming && (
        <span className="flex items-center gap-2 text-sm text-green-600">
          <span className="h-2 w-2 animate-pulse rounded-full bg-green-500" />
          Live
        </span>
      )}
    </div>
  );
}
```

### 4.5 Trace Event List Component

#### frontend/src/components/organisms/TraceEventList.tsx

```typescript
/**
 * Scrollable list of trace events.
 */

import { useRef, useEffect } from "react";
import { TraceEventItem } from "./TraceEventItem";
import type { RunEvent } from "@/types/events";

interface TraceEventListProps {
  events: RunEvent[];
  selectedIndex: number | null;
  onSelect: (index: number) => void;
}

export function TraceEventList({
  events,
  selectedIndex,
  onSelect,
}: TraceEventListProps) {
  const listRef = useRef<HTMLDivElement>(null);
  const lastEventRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to latest event
  useEffect(() => {
    if (lastEventRef.current) {
      lastEventRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [events.length]);

  return (
    <div ref={listRef} className="flex-1 overflow-y-auto">
      {events.map((event, index) => (
        <div
          key={`${event.type}-${index}`}
          ref={index === events.length - 1 ? lastEventRef : undefined}
        >
          <TraceEventItem
            event={event}
            index={index}
            isSelected={index === selectedIndex}
            onSelect={() => onSelect(index)}
          />
        </div>
      ))}
    </div>
  );
}
```

### 4.6 Trace Event Item Component

#### frontend/src/components/organisms/TraceEventItem.tsx

```typescript
/**
 * Individual event item in the trace list.
 */

import { memo } from "react";
import { cn } from "@/lib/cn";
import type { RunEvent } from "@/types/events";

interface TraceEventItemProps {
  event: RunEvent;
  index: number;
  isSelected: boolean;
  onSelect: () => void;
}

const EVENT_STYLES: Record<
  string,
  { icon: string; bgColor: string; borderColor: string }
> = {
  QuestionAsked: {
    icon: "❓",
    bgColor: "bg-blue-50",
    borderColor: "border-blue-200",
  },
  PlanCreated: {
    icon: "📋",
    bgColor: "bg-purple-50",
    borderColor: "border-purple-200",
  },
  SearchStarted: {
    icon: "🔍",
    bgColor: "bg-gray-50",
    borderColor: "border-gray-200",
  },
  SourceQueried: {
    icon: "🌐",
    bgColor: "bg-cyan-50",
    borderColor: "border-cyan-200",
  },
  EvidenceCollected: {
    icon: "📄",
    bgColor: "bg-green-50",
    borderColor: "border-green-200",
  },
  ContradictionDetected: {
    icon: "⚠️",
    bgColor: "bg-yellow-50",
    borderColor: "border-yellow-200",
  },
  AnswerDrafted: {
    icon: "✏️",
    bgColor: "bg-blue-50",
    borderColor: "border-blue-200",
  },
  JudgeVerdict: {
    icon: "⚖️",
    bgColor: "bg-purple-50",
    borderColor: "border-purple-200",
  },
  ConfidenceCalculated: {
    icon: "📊",
    bgColor: "bg-green-50",
    borderColor: "border-green-200",
  },
  CriticFeedback: {
    icon: "💬",
    bgColor: "bg-orange-50",
    borderColor: "border-orange-200",
  },
  Stopped: {
    icon: "🛑",
    bgColor: "bg-red-50",
    borderColor: "border-red-200",
  },
  ResumeStarted: {
    icon: "▶️",
    bgColor: "bg-blue-50",
    borderColor: "border-blue-200",
  },
  ForkCreated: {
    icon: "🍴",
    bgColor: "bg-purple-50",
    borderColor: "border-purple-200",
  },
};

function getEventSummary(event: RunEvent): string {
  switch (event.type) {
    case "QuestionAsked":
      return truncate((event as any).question, 50);
    case "PlanCreated":
      return `${(event as any).sub_claims?.length ?? 0} claims`;
    case "SourceQueried":
      return (event as any).source_name || "Source";
    case "EvidenceCollected":
      return `${(event as any).snippets?.length ?? 0} snippets`;
    case "JudgeVerdict":
      return `Confidence: ${((event as any).confidence * 100).toFixed(0)}%`;
    case "Stopped":
      return (event as any).reason || "Stopped";
    default:
      return event.type;
  }
}

function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str;
  return str.slice(0, maxLength).trim() + "...";
}

export const TraceEventItem = memo(function TraceEventItem({
  event,
  index,
  isSelected,
  onSelect,
}: TraceEventItemProps) {
  const styles = EVENT_STYLES[event.type] ?? {
    icon: "📌",
    bgColor: "bg-gray-50",
    borderColor: "border-gray-200",
  };

  return (
    <button
      onClick={onSelect}
      className={cn(
        "flex w-full items-start gap-3 border-b p-3 text-left transition-colors hover:bg-gray-50",
        isSelected && "bg-blue-50 hover:bg-blue-100"
      )}
    >
      {/* Timeline connector */}
      <div className="flex flex-col items-center">
        <div
          className={cn(
            "flex h-8 w-8 items-center justify-center rounded-full border text-sm",
            styles.bgColor,
            styles.borderColor
          )}
        >
          {styles.icon}
        </div>
        <div className="h-full w-0.5 bg-gray-200" />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-900">
            {event.type}
          </span>
          <span className="text-xs text-gray-500">#{index + 1}</span>
        </div>
        <p className="mt-1 truncate text-sm text-gray-600">
          {getEventSummary(event)}
        </p>
      </div>

      {/* Chevron */}
      <svg
        className="h-5 w-5 flex-shrink-0 text-gray-400"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M9 5l7 7-7 7"
        />
      </svg>
    </button>
  );
});
```

### 4.7 Trace Event Details Component

#### frontend/src/components/organisms/TraceEventDetails.tsx

```typescript
/**
 * Detailed view of a single event.
 */

import { Button } from "@/components/atoms";
import type { RunEvent } from "@/types/events";

interface TraceEventDetailsProps {
  event: RunEvent;
  index: number;
  onDiff: () => void;
}

export function TraceEventDetails({
  event,
  index,
  onDiff,
}: TraceEventDetailsProps) {
  return (
    <div className="flex-1 overflow-y-auto p-4">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <span className="text-sm text-gray-500">Event #{index + 1}</span>
        <Button variant="ghost" size="sm" onClick={onDiff}>
          Compare
        </Button>
      </div>

      {/* Event type */}
      <h3 className="mb-4 text-xl font-semibold">{event.type}</h3>

      {/* JSON data */}
      <div className="rounded-lg bg-gray-50 p-4">
        <pre className="overflow-x-auto text-sm text-gray-700">
          {JSON.stringify(event, null, 2)}
        </pre>
      </div>

      {/* Fork indicator */}
      {isForkable(event.type) && (
        <div className="mt-4 rounded-lg border border-purple-200 bg-purple-50 p-3">
          <p className="text-sm text-purple-800">
            ✨ This event is a valid fork point
          </p>
        </div>
      )}
    </div>
  );
}

function isForkable(type: string): boolean {
  return [
    "PlanCreated",
    "EvidenceCollected",
    "ContradictionDetected",
    "AnswerDrafted",
    "JudgeVerdict",
  ].includes(type);
}
```

### 4.8 Trace Diff View Component

#### frontend/src/components/organisms/TraceDiffView.tsx

```typescript
/**
 * Side-by-side event comparison view.
 */

import type { RunEvent } from "@/types/events";

interface TraceDiffViewProps {
  event1: RunEvent;
  event2: RunEvent;
  onSelectSecond: (index: number) => void;
  events: RunEvent[];
}

export function TraceDiffView({
  event1,
  event2,
  onSelectSecond,
  events,
}: TraceDiffViewProps) {
  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Event selector */}
      <div className="border-b border-gray-200 p-3">
        <label className="text-sm text-gray-600">
          Compare with event:
          <select
            className="ml-2 rounded border border-gray-300 px-2 py-1 text-sm"
            onChange={(e) => onSelectSecond(Number(e.target.value))}
          >
            {events.map((ev, i) => (
              <option key={i} value={i}>
                #{i + 1} - {ev.type}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* Side by side */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left */}
        <div className="flex-1 overflow-y-auto border-r border-gray-200 p-4">
          <h4 className="mb-2 font-medium">Event A</h4>
          <pre className="overflow-x-auto rounded bg-gray-50 p-3 text-xs">
            {JSON.stringify(event1, null, 2)}
          </pre>
        </div>

        {/* Right */}
        <div className="flex-1 overflow-y-auto p-4">
          <h4 className="mb-2 font-medium">Event B</h4>
          <pre className="overflow-x-auto rounded bg-gray-50 p-3 text-xs">
            {JSON.stringify(event2, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
}
```

---

## 5. Acceptance Criteria

### AC-01: Events Display in Order (T2)
```gherkin
Given a run with 10 events
When I view the trace panel
Then I see all 10 events in chronological order
  And each shows icon, type, and summary
```

### AC-02: Auto-Scroll to Latest
```gherkin
Given a streaming run
When a new event is emitted
Then the list scrolls to show the new event
```

### AC-03: Event Details Expand (T3)
```gherkin
Given I click on an event
When the details view opens
Then I see the full JSON payload
  And a "Compare" button
```

### AC-04: Fork Points Highlighted
```gherkin
Given an EvidenceCollected event
When I view its details
Then I see "This event is a valid fork point" indicator
```

---

## 6. Implementation Checklist

- [ ] Create `frontend/src/components/organisms/TracePanel.tsx`
- [ ] Create `frontend/src/components/organisms/TraceEventList.tsx`
- [ ] Create `frontend/src/components/organisms/TraceEventItem.tsx`
- [ ] Create `frontend/src/components/organisms/TraceEventDetails.tsx`
- [ ] Create `frontend/src/components/organisms/TraceDiffView.tsx`
- [ ] Update `ResearchPage` to use real `TracePanel`
- [ ] Write component tests
- [ ] Test auto-scroll behavior

## 7. Testing Strategy

| Test Type | Tool | Target | Coverage |
|-----------|------|--------|----------|
| Unit | Vitest + RTL | Components | 100% |
| Visual | Manual | Event colors/icons | Smoke test |

## 8. Environment Variables

_None required._

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Large JSON renders slow | Med | Low | Virtualization (V2) |
| Many events = long scroll | Low | Med | Auto-scroll + search (V2) |

## 10. Out of Scope

- Event search/filter
- Export trace
- Collapse/expand all
