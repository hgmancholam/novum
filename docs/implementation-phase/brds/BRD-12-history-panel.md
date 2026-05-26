# BRD-12: History Panel (Left Sidebar)

**Document ID:** BRD-12
**Version:** 1.0
**Status:** Draft
**Author:** BSA Agent
**Date:** 2026-05-26
**Implementation Order:** 13 of 19

---

## 1. Executive Summary

Implement the History Panel (left sidebar) showing the list of past runs with states L1-L7 from the UI prototype. Users can browse, filter, and select runs for viewing or forking.

## 2. RF Traceability

| RF | Requirement | Coverage |
|----|-------------|----------|
| RF-09 | History panel states (L1-L7) | Complete |

## 3. Dependencies

| Depends On | Required For |
|------------|--------------|
| BRD-03, BRD-04, BRD-11 | Complete |

---

## 4. Technical Specification

### 4.1 File Structure

```
frontend/
  src/
    components/
      organisms/
        HistoryPanel.tsx
        HistoryItem.tsx
        HistoryFilters.tsx
    hooks/
      useRunHistory.ts
    lib/
      api.ts                # Updated with history endpoints
```

### 4.2 States from UI Prototype

| State | Description | Implementation |
|-------|-------------|----------------|
| L1 | Empty list | Show "No runs yet" message |
| L2 | List with items | Show run cards |
| L3 | Item selected | Highlight selected run |
| L4 | Item hover | Show hover state |
| L5 | Loading | Show skeleton loaders |
| L6 | Error | Show error with retry |
| L7 | Filtered | Show active filters |

### 4.3 API Types

#### frontend/src/types/history.ts

```typescript
/**
 * History-related types.
 */

import type { StopReason } from "./events";

export interface RunSummary {
  id: string;
  question: string;
  status: "running" | "completed" | "stopped";
  stopReason?: StopReason;
  confidence?: number;
  createdAt: string;
  completedAt?: string;
  eventCount: number;
  isForked: boolean;
  forkedFromId?: string;
}

export interface HistoryFilters {
  status?: "running" | "completed" | "stopped";
  stopReason?: StopReason;
  search?: string;
}

export interface HistoryResponse {
  items: RunSummary[];
  total: number;
  hasMore: boolean;
}
```

### 4.4 API Functions

#### frontend/src/lib/api.ts (additions)

```typescript
// ... existing imports and functions ...

export interface CreateRunParams {
  question: string;
  threshold?: number;
}

export interface CreateRunResponse {
  id: string;
  question: string;
}

export async function createRun(
  params: CreateRunParams
): Promise<CreateRunResponse> {
  const response = await fetch(`${API_URL}/api/runs`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    throw new Error("Failed to create run");
  }

  return response.json();
}

export async function getRunHistory(
  filters: HistoryFilters = {},
  cursor?: string
): Promise<HistoryResponse> {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.stopReason) params.set("stop_reason", filters.stopReason);
  if (filters.search) params.set("search", filters.search);
  if (cursor) params.set("cursor", cursor);

  const response = await fetch(`${API_URL}/api/runs?${params}`, {
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error("Failed to fetch history");
  }

  return response.json();
}

export async function deleteRun(runId: string): Promise<void> {
  const response = await fetch(`${API_URL}/api/runs/${runId}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error("Failed to delete run");
  }
}
```

### 4.5 History Hook

#### frontend/src/hooks/useRunHistory.ts

```typescript
/**
 * Hook for fetching and managing run history.
 */

import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getRunHistory, deleteRun } from "@/lib/api";
import type { HistoryFilters } from "@/types/history";

export function useRunHistory(filters: HistoryFilters = {}) {
  return useInfiniteQuery({
    queryKey: ["runs", filters],
    queryFn: ({ pageParam }) => getRunHistory(filters, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) =>
      lastPage.hasMore ? lastPage.items.at(-1)?.id : undefined,
    staleTime: 30 * 1000, // 30 seconds
  });
}

export function useDeleteRun() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteRun,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["runs"] });
    },
  });
}
```

### 4.6 History Panel Component

#### frontend/src/components/organisms/HistoryPanel.tsx

```typescript
/**
 * History Panel (Left Sidebar) - RF-09
 * 
 * States:
 * L1 - Empty list
 * L2 - List with items
 * L3 - Item selected
 * L4 - Item hover
 * L5 - Loading
 * L6 - Error
 * L7 - Filtered
 */

import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Spinner } from "@/components/atoms";
import { HistoryItem } from "./HistoryItem";
import { HistoryFilters } from "./HistoryFilters";
import { useRunHistory } from "@/hooks/useRunHistory";
import { useSelectionStore } from "@/stores/selectionStore";
import type { HistoryFilters as FilterType } from "@/types/history";

export function HistoryPanel() {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<FilterType>({});
  const { selectedRunId, setSelectedRunId } = useSelectionStore();

  const {
    data,
    isLoading,
    isError,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    refetch,
  } = useRunHistory(filters);

  const runs = data?.pages.flatMap((page) => page.items) ?? [];
  const hasFilters = Object.values(filters).some(Boolean);

  const handleSelect = useCallback(
    (runId: string) => {
      setSelectedRunId(runId);
      navigate(`/research/${runId}`);
    },
    [setSelectedRunId, navigate]
  );

  const handleNewQuestion = useCallback(() => {
    navigate("/");
  }, [navigate]);

  // L5 - Loading state
  if (isLoading) {
    return (
      <div className="flex h-full flex-col">
        <div className="border-b border-gray-200 p-4">
          <h2 className="text-lg font-semibold">History</h2>
        </div>
        <div className="flex flex-1 items-center justify-center">
          <Spinner size="lg" />
        </div>
      </div>
    );
  }

  // L6 - Error state
  if (isError) {
    return (
      <div className="flex h-full flex-col">
        <div className="border-b border-gray-200 p-4">
          <h2 className="text-lg font-semibold">History</h2>
        </div>
        <div className="flex flex-1 flex-col items-center justify-center gap-4 p-4">
          <p className="text-center text-red-600">
            {error instanceof Error ? error.message : "Failed to load history"}
          </p>
          <Button onClick={() => refetch()} variant="secondary">
            Retry
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-200 p-4">
        <h2 className="text-lg font-semibold">History</h2>
        <Button size="sm" onClick={handleNewQuestion}>
          New
        </Button>
      </div>

      {/* L7 - Filters */}
      <HistoryFilters
        filters={filters}
        onChange={setFilters}
        hasFilters={hasFilters}
      />

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {/* L1 - Empty state */}
        {runs.length === 0 && (
          <div className="flex flex-col items-center justify-center p-8 text-center">
            <p className="mb-4 text-gray-500">
              {hasFilters
                ? "No runs match your filters"
                : "No research runs yet"}
            </p>
            <Button onClick={handleNewQuestion}>
              Start your first research
            </Button>
          </div>
        )}

        {/* L2, L3, L4 - List with items */}
        {runs.map((run) => (
          <HistoryItem
            key={run.id}
            run={run}
            isSelected={run.id === selectedRunId}
            onSelect={() => handleSelect(run.id)}
          />
        ))}

        {/* Load more */}
        {hasNextPage && (
          <div className="p-4">
            <Button
              variant="ghost"
              className="w-full"
              onClick={() => fetchNextPage()}
              loading={isFetchingNextPage}
            >
              Load more
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
```

### 4.7 History Item Component

#### frontend/src/components/organisms/HistoryItem.tsx

```typescript
/**
 * Individual history item with hover and selection states.
 */

import { memo } from "react";
import { Badge } from "@/components/atoms";
import { StatusBadge } from "@/components/molecules";
import { cn } from "@/lib/cn";
import type { RunSummary } from "@/types/history";

interface HistoryItemProps {
  run: RunSummary;
  isSelected: boolean;
  onSelect: () => void;
}

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diff = now.getTime() - date.getTime();

  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  return `${days}d ago`;
}

function truncateQuestion(question: string, maxLength = 60): string {
  if (question.length <= maxLength) return question;
  return question.slice(0, maxLength).trim() + "...";
}

export const HistoryItem = memo(function HistoryItem({
  run,
  isSelected,
  onSelect,
}: HistoryItemProps) {
  return (
    <button
      onClick={onSelect}
      className={cn(
        "w-full border-b border-gray-100 p-4 text-left transition-colors hover:bg-gray-50",
        // L3 - Selected state
        isSelected && "bg-blue-50 hover:bg-blue-100",
        // L4 - Hover state applied via hover:bg-gray-50
      )}
    >
      {/* Question preview */}
      <p
        className={cn(
          "mb-2 text-sm font-medium",
          isSelected ? "text-blue-900" : "text-gray-900"
        )}
      >
        {truncateQuestion(run.question)}
      </p>

      {/* Metadata row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <StatusBadge status={run.status} stopReason={run.stopReason} />
          {run.isForked && (
            <Badge variant="secondary" className="text-xs">
              Fork
            </Badge>
          )}
        </div>
        <span className="text-xs text-gray-500">
          {formatRelativeTime(run.createdAt)}
        </span>
      </div>

      {/* Confidence (if available) */}
      {run.confidence !== undefined && (
        <div className="mt-2 flex items-center gap-2">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-gray-200">
            <div
              className={cn(
                "h-full rounded-full",
                run.confidence >= 0.7 ? "bg-green-500" : "bg-yellow-500"
              )}
              style={{ width: `${run.confidence * 100}%` }}
            />
          </div>
          <span className="text-xs text-gray-500">
            {Math.round(run.confidence * 100)}%
          </span>
        </div>
      )}
    </button>
  );
});
```

### 4.8 History Filters Component

#### frontend/src/components/organisms/HistoryFilters.tsx

```typescript
/**
 * History filter controls.
 */

import { useCallback } from "react";
import { Badge, Button } from "@/components/atoms";
import type { HistoryFilters as FilterType } from "@/types/history";
import type { StopReason } from "@/types/events";

interface HistoryFiltersProps {
  filters: FilterType;
  onChange: (filters: FilterType) => void;
  hasFilters: boolean;
}

const statusOptions: Array<{
  value: FilterType["status"];
  label: string;
}> = [
  { value: "running", label: "Running" },
  { value: "completed", label: "Completed" },
  { value: "stopped", label: "Stopped" },
];

const stopReasonOptions: Array<{ value: StopReason; label: string }> = [
  { value: "judge_confirmed", label: "Confirmed" },
  { value: "honest_unanswerable", label: "Unanswerable" },
  { value: "honest_contradiction", label: "Contradiction" },
  { value: "honest_ambiguous", label: "Ambiguous" },
  { value: "user_cancelled", label: "Cancelled" },
];

export function HistoryFilters({
  filters,
  onChange,
  hasFilters,
}: HistoryFiltersProps) {
  const handleStatusToggle = useCallback(
    (status: FilterType["status"]) => {
      onChange({
        ...filters,
        status: filters.status === status ? undefined : status,
      });
    },
    [filters, onChange]
  );

  const handleClear = useCallback(() => {
    onChange({});
  }, [onChange]);

  return (
    <div className="border-b border-gray-200 p-3">
      {/* Search */}
      <input
        type="text"
        placeholder="Search questions..."
        value={filters.search ?? ""}
        onChange={(e) => onChange({ ...filters, search: e.target.value || undefined })}
        className="mb-3 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
      />

      {/* Status filters */}
      <div className="mb-2 flex flex-wrap gap-1">
        {statusOptions.map(({ value, label }) => (
          <button
            key={value}
            onClick={() => handleStatusToggle(value)}
            className={`rounded-full px-2 py-1 text-xs transition-colors ${
              filters.status === value
                ? "bg-blue-600 text-white"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Clear button */}
      {hasFilters && (
        <Button variant="ghost" size="sm" onClick={handleClear} className="mt-2 w-full">
          Clear filters
        </Button>
      )}
    </div>
  );
}
```

---

## 5. Acceptance Criteria

### AC-01: Empty State (L1)
```gherkin
Given no runs exist for the user
When I view the history panel
Then I see "No research runs yet" message
  And a "Start your first research" button
```

### AC-02: Run List Displays (L2)
```gherkin
Given I have 5 completed runs
When I view the history panel
Then I see 5 run items with question previews
  And each shows status badge and time
```

### AC-03: Selection Highlights (L3)
```gherkin
Given I click on a run in the history
When the run is selected
Then it has a blue background
  And the URL updates to /research/{runId}
```

### AC-04: Infinite Scroll Works
```gherkin
Given I have 50 runs
When I scroll to the bottom
Then a "Load more" button appears
  And clicking it loads the next page
```

---

## 6. Implementation Checklist

- [ ] Create `frontend/src/types/history.ts`
- [ ] Update `frontend/src/lib/api.ts` with history endpoints
- [ ] Create `frontend/src/hooks/useRunHistory.ts`
- [ ] Create `frontend/src/components/organisms/HistoryPanel.tsx`
- [ ] Create `frontend/src/components/organisms/HistoryItem.tsx`
- [ ] Create `frontend/src/components/organisms/HistoryFilters.tsx`
- [ ] Update `ResearchPage` to use real `HistoryPanel`
- [ ] Write component tests
- [ ] Test infinite scroll

## 7. Testing Strategy

| Test Type | Tool | Target | Coverage |
|-----------|------|--------|----------|
| Unit | Vitest + RTL | Components | 100% |
| Integration | Vitest + MSW | API calls | 100% |

## 8. Environment Variables

_None required._

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Slow history query | Med | Low | Pagination + cursor |

## 10. Out of Scope

- Bulk delete
- Export history
- Sorting options
