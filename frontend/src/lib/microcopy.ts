/**
 * Microcopy strings — centralised so tests and components share the
 * same wording. Per `ui-prototype.md §7`, user-facing strings must be
 * reused verbatim.
 */

export const POST_RESUME_NOTICE =
  "Resume recorded. Agent restart will land in a future iteration — refresh the page to see new events as they arrive.";

export const FORK_MODAL_EMPTY_STATE =
  "No forkable points yet — wait for the agent to reach a plan or contradiction.";

export const FORK_MODAL_TITLE = "Fork from a decision point";

export const FORK_MODAL_DESCRIPTION =
  "Pick the event you want to branch from. The new run will replay the trace up to (and including) that point, then continue independently.";

export const LINEAGE_BADGE_LABEL = "Forked from earlier run";

export const RATE_LIMIT_MODAL_TITLE = "The LLM provider is rate-limiting us";

export const RATE_LIMIT_MODAL_DESCRIPTION =
  "The selected LLM provider returned a quota / 429 error and the run was stopped. This is a temporary limit from the provider — not a bug in the app. Per-minute windows usually reset in under a minute; daily free-tier quotas reset on the provider's UTC clock.";

export const RATE_LIMIT_MODAL_HINT =
  "Pick a different provider from the header chip, or wait for the quota window to reset and try again.";

export const RATE_LIMIT_MODAL_CLOSE = "Got it";

// Feed microcopy
export const FEED_LET_ME_SEARCH = "Let me search for {query}…";
export const FEED_LET_ME_FETCH = "Let me read this page…";
export const FEED_LET_ME_THINK = "Let me think this through…";
export const FEED_SEARCHED_WEB = "Searched the web";
export const FEED_FETCHED_PAGE = "Read the page";
export const FEED_DONE = "Done";
export const FEED_TOGGLE_COLLAPSE = "Hide reasoning";
export const FEED_TOGGLE_EXPAND = "Show reasoning";
export const TRACE_PANEL_COLLAPSE = "Collapse trace";
export const TRACE_PANEL_EXPAND = "Expand trace";
export const ANSWER_SKIP_HINT = "Click to skip";
export const ANSWER_ANIMATE_TOGGLE = "Animate answer";

export function FEED_RESULTS_COUNT(n: number): string {
  return n === 1 ? "1 result" : `${n.toString()} results`;
}

export function FEED_REASONING_TRACE(stepCount: number, seconds: number): string {
  const stepLabel = stepCount === 1 ? "step" : "steps";
  return `Reasoning (${stepCount.toString()} ${stepLabel} · ${seconds.toString()}s)`;
}
