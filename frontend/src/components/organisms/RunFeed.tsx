/**
 * RunFeed organism — AnatomyOfARun-style stepper for live reasoning.
 *
 * Visual model: `pages/HowWeWorkPage.tsx::AnatomyOfARun`. A vertical rail
 * with small glowing dots; each row is an uppercase colored label + inline
 * detail. The latest active step types out via `useTypewriter`. While the
 * run is streaming, a bottom row shows `ThinkingDots` + the current
 * activity narrative + a rotating idle reassurance message.
 */

/* eslint-disable @typescript-eslint/no-unnecessary-condition */

import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "motion/react";
import {
  buildFeedSteps,
  type FeedStepData,
  type RunStreamEvent,
} from "@/lib/feedGrouping";
import { FeedRail, JumpToLatestPill, CollapseToggleButton, ThinkingDots } from "@/components/atoms";
import { FeedStepLine } from "@/components/molecules";
import {
  FEED_TOGGLE_COLLAPSE,
  FEED_TOGGLE_EXPAND,
  FEED_REASONING_TRACE,
} from "@/lib/microcopy";
import { useIdleReassurance } from "@/lib/idleMessages";
import { getEventActivity, getEventLabel, getEventNarrative } from "@/lib/eventLabels";
import { getEventVisual, TONE_COLOR } from "@/lib/eventVisuals";
import type { EventType } from "@/types/events";
import { cn } from "@/lib/cn";

export interface RunFeedProps {
  events: readonly RunStreamEvent[];
  isComplete: boolean;
  className?: string | undefined;
}

const FEED_COLLAPSED_KEY = "novum_run_feed_collapsed";

function getInitialCollapsed(isComplete: boolean): boolean {
  if (!isComplete) return false;
  try {
    return localStorage.getItem(FEED_COLLAPSED_KEY) === "1";
  } catch {
    return true;
  }
}

function persistCollapsed(value: boolean): void {
  try {
    localStorage.setItem(FEED_COLLAPSED_KEY, value ? "1" : "0");
  } catch {
    // ignore
  }
}

interface StepView {
  label: string;
  detail: string;
  accent: string;
  children?: ReactNode;
}

function hostnameOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function mapStepToView(step: FeedStepData): StepView {
  const payload = step.payload;
  const type = (payload.type as string | undefined) ?? "";

  switch (step.kind) {
    case "plan": {
      const rationale = (payload.rationale as string | undefined) ?? "";
      const subClaims =
        (payload.sub_claims as Array<{ text?: string }> | undefined) ?? [];
      const isRevision = type === "PlanRevised";
      const label = isRevision ? "Plan revised" : "Plan";
      const summary =
        rationale.length > 0
          ? rationale
          : isRevision
            ? "Rethought the approach after reviewing the findings."
            : "Drafted the search plan.";
      const detail =
        subClaims.length > 0
          ? `${summary} I'll verify ${subClaims.length.toString()} sub-claim${subClaims.length === 1 ? "" : "s"}.`
          : summary;
      const children: ReactNode =
        subClaims.length > 0 ? (
          <ul className="mt-1 flex flex-wrap gap-1.5">
            {subClaims.map((c, idx) => (
              <li
                key={idx}
                className="rounded-full border border-[var(--glass-border)] bg-[var(--glass-bg)] px-2.5 py-0.5 text-[11px] text-[var(--text-secondary)]"
              >
                {c.text ?? `Sub-claim ${(idx + 1).toString()}`}
              </li>
            ))}
          </ul>
        ) : null;
      return {
        label,
        detail,
        accent: "var(--accent)",
        ...(children !== null ? { children } : {}),
      };
    }
    case "search": {
      const query = (payload.query as string | undefined) ?? "";
      const sources =
        (payload.sources as Array<{ url?: string; title?: string }> | undefined) ?? [];
      const detail =
        query.length > 0
          ? `Searched the web: "${query}" → ${sources.length.toString()} source${sources.length === 1 ? "" : "s"}.`
          : `Found ${sources.length.toString()} source${sources.length === 1 ? "" : "s"}.`;
      const children: ReactNode =
        sources.length > 0 ? (
          <ul className="mt-1 space-y-1">
            {sources.slice(0, 5).map((s, idx) => (
              <motion.li
                key={`${s.url ?? ""}-${idx.toString()}`}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.25, delay: idx * 0.08, ease: "easeOut" }}
                className="flex items-baseline gap-2 text-[12px] text-[var(--text-secondary)]"
              >
                <span className="h-1 w-1 shrink-0 rounded-full bg-[#22d3ee]" />
                {s.url ? (
                  <a
                    href={s.url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="truncate hover:text-[var(--text-primary)] hover:underline"
                  >
                    {s.title && s.title.length > 0 ? s.title : hostnameOf(s.url)}
                    <span className="ml-1.5 text-[var(--text-muted)]">
                      ({hostnameOf(s.url)})
                    </span>
                  </a>
                ) : (
                  <span className="truncate">{s.title ?? "Source"}</span>
                )}
              </motion.li>
            ))}
            {sources.length > 5 ? (
              <li className="text-[11px] text-[var(--text-muted)]">
                +{(sources.length - 5).toString()} more…
              </li>
            ) : null}
          </ul>
        ) : null;
      return {
        label: "Search",
        accent: "#22d3ee",
        detail,
        ...(children !== null ? { children } : {}),
      };
    }
    case "judge": {
      const passed = (payload.passed as boolean | undefined) ?? false;
      const finalConfidence = (payload.final_confidence as number | undefined) ?? 0;
      const threshold = (payload.threshold as number | undefined) ?? 0.7;
      const rationale = (payload.rationale as string | undefined) ?? "";
      const verdict = passed ? "Confirmed" : "Retry suggested";
      const detail = `Verdict: ${verdict} · confidence ${(finalConfidence * 100).toFixed(0)}% (threshold ${(threshold * 100).toFixed(0)}%).`;
      const children: ReactNode =
        rationale.length > 0 ? (
          <p className="mt-1 text-[12px] italic text-[var(--text-muted)]">
            «{rationale}»
          </p>
        ) : null;
      return {
        label: "Judge",
        accent: "var(--warm)",
        detail,
        ...(children !== null ? { children } : {}),
      };
    }
    case "ambiguity":
      return {
        label: "Ambiguity",
        accent: "var(--semantic-warning)",
        detail: "Detected that the question has multiple possible interpretations.",
      };
    case "contradiction":
      return {
        label: "Contradiction",
        accent: "var(--semantic-warning)",
        detail: "The sources disagree on key data.",
      };
    case "done": {
      const stopReason = (payload.stop_reason as string | undefined) ?? "unknown";
      const confirmed = stopReason === "judge_confirmed";
      return {
        label: "Verified result",
        accent: confirmed ? "var(--semantic-success)" : "var(--semantic-neutral)",
        detail: `Done — reason: ${stopReason}.`,
      };
    }
    default: {
      const tone = getEventVisual(type).tone;
      const accent = TONE_COLOR[tone];
      const label = getEventLabel(type);
      const detail = type
        ? getEventNarrative(type as EventType, payload)
        : getEventActivity(undefined);
      return { label, detail, accent };
    }
  }
}

function getActivityText(events: readonly RunStreamEvent[]): string {
  for (let i = events.length - 1; i >= 0; i--) {
    const ev = events[i];
    if (ev !== undefined) {
      return getEventActivity(ev.type);
    }
  }
  return getEventActivity(undefined);
}

export function RunFeed({ events, isComplete, className }: RunFeedProps) {
  const steps = useMemo(
    () => buildFeedSteps(events as RunStreamEvent[], { isComplete }),
    [events, isComplete]
  );

  const [isCollapsed, setIsCollapsed] = useState(() =>
    getInitialCollapsed(isComplete)
  );
  const [sticky, setSticky] = useState(true);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (isComplete) {
      setIsCollapsed(getInitialCollapsed(true));
    }
  }, [isComplete]);

  useEffect(() => {
    const sentinel = bottomRef.current;
    if (!sentinel || typeof IntersectionObserver === "undefined") {
      setSticky(true);
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry) setSticky(entry.isIntersecting);
      },
      { threshold: 0.5 }
    );
    observer.observe(sentinel);
    return () => {
      observer.disconnect();
    };
  }, []);

  useEffect(() => {
    if (sticky && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [events.length, sticky]);

  function handleJumpToLatest(): void {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }

  function toggleCollapsed(): void {
    const newValue = !isCollapsed;
    setIsCollapsed(newValue);
    persistCollapsed(newValue);
  }

  const lastEvent = events[events.length - 1];
  const lastTimestamp: number = lastEvent?.timestamp_ms ?? 0;

  const idleMessage = useIdleReassurance(
    !isComplete && events.length > 0,
    lastTimestamp > 0 ? lastTimestamp : null,
  );

  const activityText = !isComplete ? getActivityText(events) : "";

  if (events.length === 0) {
    return null;
  }

  return (
    <div
      ref={containerRef}
      data-testid="run-feed"
      className={cn("relative", className)}
    >
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-[var(--glass-border)] px-1 pb-3">
        <span
          className={cn(
            "inline-flex h-2 w-2 rounded-full",
            isComplete
              ? "bg-[var(--semantic-success)] shadow-[0_0_8px_rgba(16,185,129,0.6)]"
              : "bg-[var(--accent)] shadow-[0_0_8px_var(--accent-glow)] animate-pulse"
          )}
        />
        <h3 className="text-sm font-medium text-[var(--text-secondary)]">
          {steps.length > 0
            ? FEED_REASONING_TRACE(steps.length, isComplete)
            : "Thinking…"}
        </h3>
        {isComplete && steps.length > 0 ? (
          <div className="ml-auto">
            <CollapseToggleButton
              isCollapsed={isCollapsed}
              onToggle={toggleCollapsed}
              labelCollapse={FEED_TOGGLE_COLLAPSE}
              labelExpand={FEED_TOGGLE_EXPAND}
            />
          </div>
        ) : null}
      </div>

      {/* Feed content */}
      {!isCollapsed ? (
        <div className="relative pt-5 pb-2 pl-7 pr-1">
          <FeedRail tone={isComplete ? "neutral" : "active"} />
          <ol className="relative">
            {steps.map((step, idx) => {
              const view = mapStepToView(step);
              const isLatest = idx === steps.length - 1;
              const enableTypewriter = isLatest && !isComplete;
              return (
                <FeedStepLine
                  key={`step-${idx.toString()}-${step.kind}`}
                  label={view.label}
                  detail={view.detail}
                  accent={view.accent}
                  deltaMs={step.deltaMs}
                  typewriter={enableTypewriter}
                  isLast={isLatest && isComplete}
                >
                  {view.children}
                </FeedStepLine>
              );
            })}
            {!isComplete ? (
              <ThinkingRow activity={activityText} idleMessage={idleMessage} />
            ) : null}
          </ol>
          <div ref={bottomRef} />
        </div>
      ) : null}

      {!sticky && !isCollapsed ? (
        <div className="absolute bottom-4 right-4 z-10">
          <JumpToLatestPill onClick={handleJumpToLatest} />
        </div>
      ) : null}
    </div>
  );
}

interface ThinkingRowProps {
  activity: string;
  idleMessage: string | null;
}

function ThinkingRow({ activity, idleMessage }: ThinkingRowProps) {
  return (
    <motion.li
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
      className="relative pt-1"
      data-testid="feed-thinking-row"
    >
      <span
        aria-hidden
        className="absolute top-2 -left-[22px] inline-flex h-3.5 w-3.5 items-center justify-center rounded-full"
        style={{
          background: "color-mix(in srgb, var(--accent) 35%, var(--bg-primary))",
          boxShadow: "0 0 0 3px var(--bg-primary), 0 0 12px var(--accent-glow)",
        }}
      />
      <div className="flex items-center gap-2">
        <ThinkingDots />
        <span className="text-sm italic text-[var(--text-secondary)]">
          {activity}…
        </span>
      </div>
      {idleMessage !== null ? (
        <p
          data-testid="feed-idle-message"
          className="mt-1.5 text-xs italic text-[var(--text-muted)] animate-pulse"
        >
          {idleMessage}
        </p>
      ) : null}
    </motion.li>
  );
}
