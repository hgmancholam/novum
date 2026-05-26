# BRD-11: Frontend Setup & Layout Shell

**Document ID:** BRD-11
**Version:** 1.0
**Status:** Draft
**Author:** BSA Agent
**Date:** 2026-05-26
**Implementation Order:** 12 of 19

---

## 1. Executive Summary

Set up the React frontend with 3-column responsive layout shell as defined in the UI prototype. This BRD covers the Vite + React + Tailwind v4 setup, atomic design structure, and the main layout component with responsive behavior.

## 2. RF Traceability

| RF | Requirement | Coverage |
|----|-------------|----------|
| RF-13 | UI surfaces every trust guarantee | Layout foundation |
| UI Prototype | 3-column layout (L+C+R) | Complete |

## 3. Dependencies

| Depends On | Required For |
|------------|--------------|
| BRD-00 | BRD-12, BRD-13, BRD-14 |

---

## 4. Technical Specification

### 4.1 File Structure

```
frontend/
  src/
    components/
      atoms/
        Button.tsx
        Badge.tsx
        Spinner.tsx
        Icon.tsx
        index.ts
      molecules/
        SearchInput.tsx
        ConfidenceBar.tsx
        StatusBadge.tsx
        index.ts
      organisms/
        Header.tsx
        HistoryPanel.tsx        # (BRD-12)
        CenterPanel.tsx         # (BRD-13)
        TracePanel.tsx          # (BRD-14)
        index.ts
      templates/
        MainLayout.tsx
        index.ts
      pages/
        HomePage.tsx
        ResearchPage.tsx
        index.ts
    stores/
      selectionStore.ts
    lib/
      cn.ts                     # clsx + tailwind-merge
    App.tsx
    main.tsx
    index.css
```

### 4.2 Utility Function

#### frontend/src/lib/cn.ts

```typescript
/**
 * Utility to merge Tailwind classes.
 */

import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
```

### 4.3 Atoms

#### frontend/src/components/atoms/Button.tsx

```typescript
/**
 * Button atom with variants.
 */

import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = "primary",
      size = "md",
      loading = false,
      disabled,
      children,
      ...props
    },
    ref
  ) => {
    const baseStyles =
      "inline-flex items-center justify-center font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 rounded-md";

    const variants = {
      primary: "bg-blue-600 text-white hover:bg-blue-700",
      secondary: "bg-gray-200 text-gray-900 hover:bg-gray-300",
      ghost: "hover:bg-gray-100",
      danger: "bg-red-600 text-white hover:bg-red-700",
    };

    const sizes = {
      sm: "h-8 px-3 text-sm",
      md: "h-10 px-4 text-sm",
      lg: "h-12 px-6 text-base",
    };

    return (
      <button
        ref={ref}
        className={cn(baseStyles, variants[variant], sizes[size], className)}
        disabled={disabled || loading}
        {...props}
      >
        {loading && (
          <svg
            className="mr-2 h-4 w-4 animate-spin"
            viewBox="0 0 24 24"
            fill="none"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
        )}
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";
```

#### frontend/src/components/atoms/Badge.tsx

```typescript
/**
 * Badge atom for status indicators.
 */

import { cn } from "@/lib/cn";

interface BadgeProps {
  variant?:
    | "default"
    | "success"
    | "warning"
    | "error"
    | "info"
    | "secondary";
  children: React.ReactNode;
  className?: string;
}

const variants = {
  default: "bg-gray-100 text-gray-800",
  success: "bg-green-100 text-green-800",
  warning: "bg-yellow-100 text-yellow-800",
  error: "bg-red-100 text-red-800",
  info: "bg-blue-100 text-blue-800",
  secondary: "bg-gray-200 text-gray-600",
};

export function Badge({
  variant = "default",
  children,
  className,
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        variants[variant],
        className
      )}
    >
      {children}
    </span>
  );
}
```

#### frontend/src/components/atoms/Spinner.tsx

```typescript
/**
 * Loading spinner atom.
 */

import { cn } from "@/lib/cn";

interface SpinnerProps {
  size?: "sm" | "md" | "lg";
  className?: string;
}

const sizes = {
  sm: "h-4 w-4",
  md: "h-6 w-6",
  lg: "h-8 w-8",
};

export function Spinner({ size = "md", className }: SpinnerProps) {
  return (
    <svg
      className={cn("animate-spin text-gray-500", sizes[size], className)}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}
```

#### frontend/src/components/atoms/index.ts

```typescript
export { Button } from "./Button";
export { Badge } from "./Badge";
export { Spinner } from "./Spinner";
```

### 4.4 Molecules

#### frontend/src/components/molecules/ConfidenceBar.tsx

```typescript
/**
 * Confidence visualization bar.
 */

import { cn } from "@/lib/cn";

interface ConfidenceBarProps {
  value: number; // 0-1
  threshold?: number; // 0-1
  showLabel?: boolean;
  className?: string;
}

export function ConfidenceBar({
  value,
  threshold = 0.7,
  showLabel = true,
  className,
}: ConfidenceBarProps) {
  const percentage = Math.round(value * 100);
  const passed = value >= threshold;

  return (
    <div className={cn("w-full", className)}>
      {showLabel && (
        <div className="mb-1 flex justify-between text-sm">
          <span className="text-gray-600">Confidence</span>
          <span
            className={cn(
              "font-medium",
              passed ? "text-green-600" : "text-yellow-600"
            )}
          >
            {percentage}%
          </span>
        </div>
      )}
      <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200">
        <div
          className={cn(
            "h-full transition-all duration-300",
            passed ? "bg-green-500" : "bg-yellow-500"
          )}
          style={{ width: `${percentage}%` }}
        />
        {/* Threshold marker */}
        <div
          className="absolute h-2 w-0.5 bg-gray-600"
          style={{ left: `${threshold * 100}%` }}
        />
      </div>
    </div>
  );
}
```

#### frontend/src/components/molecules/StatusBadge.tsx

```typescript
/**
 * Status badge for run states and stop reasons.
 */

import { Badge } from "@/components/atoms";
import type { StopReason } from "@/types/events";

interface StatusBadgeProps {
  status: "running" | "completed" | "stopped";
  stopReason?: StopReason;
}

const stopReasonLabels: Record<StopReason, string> = {
  judge_confirmed: "Confirmed",
  honest_unanswerable: "Unanswerable",
  honest_contradiction: "Contradiction",
  honest_ambiguous: "Ambiguous",
  stopped_by_budget: "Budget",
  user_cancelled: "Cancelled",
  errored: "Error",
};

const stopReasonVariants: Record<
  StopReason,
  "success" | "warning" | "error" | "info"
> = {
  judge_confirmed: "success",
  honest_unanswerable: "warning",
  honest_contradiction: "warning",
  honest_ambiguous: "warning",
  stopped_by_budget: "info",
  user_cancelled: "secondary" as "info",
  errored: "error",
};

export function StatusBadge({ status, stopReason }: StatusBadgeProps) {
  if (status === "running") {
    return <Badge variant="info">Running</Badge>;
  }

  if (stopReason) {
    return (
      <Badge variant={stopReasonVariants[stopReason]}>
        {stopReasonLabels[stopReason]}
      </Badge>
    );
  }

  return <Badge variant="default">Unknown</Badge>;
}
```

#### frontend/src/components/molecules/index.ts

```typescript
export { ConfidenceBar } from "./ConfidenceBar";
export { StatusBadge } from "./StatusBadge";
```

### 4.5 Main Layout Template

#### frontend/src/components/templates/MainLayout.tsx

```typescript
/**
 * Main 3-column layout template.
 * 
 * Structure:
 * - Left: History Panel (collapsible on mobile)
 * - Center: Question + Answer
 * - Right: Trace Panel (collapsible on mobile)
 * 
 * Responsive:
 * - Desktop (≥1024px): All 3 columns visible
 * - Tablet (768-1023px): Center + toggleable panels
 * - Mobile (<768px): Center only, slide-out panels
 */

import { useState } from "react";
import { cn } from "@/lib/cn";

interface MainLayoutProps {
  leftPanel: React.ReactNode;
  centerPanel: React.ReactNode;
  rightPanel: React.ReactNode;
}

export function MainLayout({
  leftPanel,
  centerPanel,
  rightPanel,
}: MainLayoutProps) {
  const [leftOpen, setLeftOpen] = useState(false);
  const [rightOpen, setRightOpen] = useState(false);

  return (
    <div className="flex h-screen w-full overflow-hidden bg-gray-50">
      {/* Mobile overlay */}
      {(leftOpen || rightOpen) && (
        <div
          className="fixed inset-0 z-20 bg-black/50 lg:hidden"
          onClick={() => {
            setLeftOpen(false);
            setRightOpen(false);
          }}
        />
      )}

      {/* Left Panel - History */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-30 w-72 transform bg-white shadow-lg transition-transform lg:relative lg:z-0 lg:shadow-none",
          leftOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        )}
      >
        <div className="flex h-full flex-col border-r border-gray-200">
          {leftPanel}
        </div>
      </aside>

      {/* Center Panel - Main Content */}
      <main className="flex flex-1 flex-col overflow-hidden">
        {/* Mobile header with toggles */}
        <header className="flex items-center justify-between border-b border-gray-200 bg-white px-4 py-3 lg:hidden">
          <button
            onClick={() => setLeftOpen(true)}
            className="rounded-md p-2 hover:bg-gray-100"
            aria-label="Open history"
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
                d="M4 6h16M4 12h16M4 18h16"
              />
            </svg>
          </button>
          <span className="text-lg font-semibold">Novum</span>
          <button
            onClick={() => setRightOpen(true)}
            className="rounded-md p-2 hover:bg-gray-100"
            aria-label="Open trace"
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
                d="M9 5l7 7-7 7"
              />
            </svg>
          </button>
        </header>
        <div className="flex-1 overflow-auto">{centerPanel}</div>
      </main>

      {/* Right Panel - Trace */}
      <aside
        className={cn(
          "fixed inset-y-0 right-0 z-30 w-80 transform bg-white shadow-lg transition-transform lg:relative lg:z-0 lg:shadow-none",
          rightOpen ? "translate-x-0" : "translate-x-full lg:translate-x-0"
        )}
      >
        <div className="flex h-full flex-col border-l border-gray-200">
          {rightPanel}
        </div>
      </aside>
    </div>
  );
}
```

### 4.6 Selection Store

#### frontend/src/stores/selectionStore.ts

```typescript
/**
 * Selection state store for UI interactions.
 */

import { create } from "zustand";

interface SelectionState {
  // Currently selected run
  selectedRunId: string | null;
  setSelectedRunId: (id: string | null) => void;

  // Currently selected event (for trace highlighting)
  selectedEventId: number | null;
  setSelectedEventId: (id: number | null) => void;

  // Panel visibility (for mobile)
  leftPanelOpen: boolean;
  rightPanelOpen: boolean;
  toggleLeftPanel: () => void;
  toggleRightPanel: () => void;
  closePanels: () => void;
}

export const useSelectionStore = create<SelectionState>((set) => ({
  selectedRunId: null,
  setSelectedRunId: (id) => set({ selectedRunId: id }),

  selectedEventId: null,
  setSelectedEventId: (id) => set({ selectedEventId: id }),

  leftPanelOpen: false,
  rightPanelOpen: false,
  toggleLeftPanel: () =>
    set((state) => ({ leftPanelOpen: !state.leftPanelOpen })),
  toggleRightPanel: () =>
    set((state) => ({ rightPanelOpen: !state.rightPanelOpen })),
  closePanels: () => set({ leftPanelOpen: false, rightPanelOpen: false }),
}));
```

### 4.7 App Entry Point

#### frontend/src/App.tsx

```typescript
/**
 * Main application entry point.
 */

import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { HomePage, ResearchPage } from "@/components/pages";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60, // 1 minute
      retry: 1,
    },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/research/:runId" element={<ResearchPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
```

### 4.8 Home Page (Initial)

#### frontend/src/components/pages/HomePage.tsx

```typescript
/**
 * Home page with new question input.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/atoms";
import { createRun } from "@/lib/api";

export function HomePage() {
  const [question, setQuestion] = useState("");
  const navigate = useNavigate();

  const mutation = useMutation({
    mutationFn: createRun,
    onSuccess: (data) => {
      navigate(`/research/${data.id}`);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (question.trim()) {
      mutation.mutate({ question: question.trim() });
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-2xl">
        <h1 className="mb-8 text-center text-4xl font-bold text-gray-900">
          Novum
        </h1>
        <p className="mb-8 text-center text-lg text-gray-600">
          Research agent that gathers evidence and decides when it knows enough
        </p>
        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask a research question..."
              className="w-full resize-none rounded-lg border border-gray-300 p-4 text-lg focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
              rows={3}
            />
          </div>
          <Button
            type="submit"
            size="lg"
            className="w-full"
            loading={mutation.isPending}
            disabled={!question.trim()}
          >
            Start Research
          </Button>
        </form>
        {mutation.isError && (
          <p className="mt-4 text-center text-red-600">
            Error starting research. Please try again.
          </p>
        )}
      </div>
    </div>
  );
}
```

#### frontend/src/components/pages/ResearchPage.tsx

```typescript
/**
 * Research page with 3-column layout.
 */

import { useParams } from "react-router-dom";
import { MainLayout } from "@/components/templates";
import { useSelectionStore } from "@/stores/selectionStore";

// Placeholders until BRD-12, BRD-13, BRD-14
function HistoryPanelPlaceholder() {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-gray-200 p-4">
        <h2 className="text-lg font-semibold">History</h2>
      </div>
      <div className="flex-1 p-4">
        <p className="text-gray-500">Run history will appear here</p>
      </div>
    </div>
  );
}

function CenterPanelPlaceholder() {
  const { runId } = useParams<{ runId: string }>();
  return (
    <div className="flex h-full flex-col items-center justify-center p-8">
      <h2 className="mb-4 text-xl font-semibold">Research Run</h2>
      <p className="text-gray-600">Run ID: {runId}</p>
    </div>
  );
}

function TracePanelPlaceholder() {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-gray-200 p-4">
        <h2 className="text-lg font-semibold">Trace</h2>
      </div>
      <div className="flex-1 p-4">
        <p className="text-gray-500">Event trace will appear here</p>
      </div>
    </div>
  );
}

export function ResearchPage() {
  return (
    <MainLayout
      leftPanel={<HistoryPanelPlaceholder />}
      centerPanel={<CenterPanelPlaceholder />}
      rightPanel={<TracePanelPlaceholder />}
    />
  );
}
```

#### frontend/src/components/pages/index.ts

```typescript
export { HomePage } from "./HomePage";
export { ResearchPage } from "./ResearchPage";
```

---

## 5. UI Layout Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                         NOVUM                                   │
├──────────────┬───────────────────────────────┬─────────────────┤
│              │                               │                 │
│   History    │         Center Panel          │   Trace Panel   │
│   Panel      │                               │                 │
│   (w-72)     │         (flex-1)              │   (w-80)        │
│              │                               │                 │
│  - Run list  │   - Question display          │  - Event list   │
│  - Filters   │   - Answer (streaming)        │  - Details      │
│  - Stats     │   - Actions (fork/cancel)     │  - Diff view    │
│              │                               │                 │
│              │                               │                 │
└──────────────┴───────────────────────────────┴─────────────────┘
```

---

## 6. Acceptance Criteria

### AC-01: Three Columns on Desktop
```gherkin
Given a desktop viewport (≥1024px)
When I view the research page
Then I see 3 columns side by side
  And left panel is 288px (w-72)
  And right panel is 320px (w-80)
  And center panel fills remaining space
```

### AC-02: Mobile Shows Center Only
```gherkin
Given a mobile viewport (<768px)
When I view the research page
Then only the center panel is visible
  And I see toggle buttons in the header
```

### AC-03: Mobile Panels Slide Out
```gherkin
Given a mobile viewport
When I tap the history toggle
Then the left panel slides in from the left
  And a dark overlay appears behind it
```

---

## 7. Implementation Checklist

- [ ] Create `frontend/src/lib/cn.ts`
- [ ] Create atoms (Button, Badge, Spinner)
- [ ] Create molecules (ConfidenceBar, StatusBadge)
- [ ] Create `frontend/src/components/templates/MainLayout.tsx`
- [ ] Create `frontend/src/stores/selectionStore.ts`
- [ ] Create `frontend/src/components/pages/HomePage.tsx`
- [ ] Create `frontend/src/components/pages/ResearchPage.tsx`
- [ ] Update `frontend/src/App.tsx` with routing
- [ ] Write component tests
- [ ] Test responsive behavior

## 8. Testing Strategy

| Test Type | Tool | Target | Coverage |
|-----------|------|--------|----------|
| Unit | Vitest + RTL | Components | 100% |
| Visual | Manual | Responsive layout | Smoke test |

## 9. Environment Variables

_None required beyond VITE_API_URL._

## 10. Out of Scope

- Dark mode (V2)
- Keyboard navigation (accessibility V2)
- Animation polish
