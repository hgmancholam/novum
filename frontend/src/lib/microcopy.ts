/**
 * Microcopy strings — IP-15 (Fork & Resume).
 *
 * Centralised so tests and components share the same wording. Per
 * `ui-prototype.md §7`, user-facing strings must be reused verbatim.
 */

export const POST_RESUME_NOTICE =
  "Resume recorded. Agent restart will land in a future iteration — refresh the page to see new events as they arrive.";

export const FORK_MODAL_EMPTY_STATE =
  "No forkable points yet — wait for the agent to reach a plan or contradiction.";

export const FORK_MODAL_TITLE = "Fork from a decision point";

export const FORK_MODAL_DESCRIPTION =
  "Pick the event you want to branch from. The new run will replay the trace up to (and including) that point, then continue independently.";

export const LINEAGE_BADGE_LABEL = "Forked from earlier run";

export const RATE_LIMIT_MODAL_TITLE = "AI providers are rate-limiting us";

export const RATE_LIMIT_MODAL_DESCRIPTION =
  "All GitHub Models tokens in our pool returned 429 (Too Many Requests). This is a temporary quota limit from the provider — not a bug in the app. The per-minute window typically resets in under a minute; the daily quota resets at 00:00 UTC.";

export const RATE_LIMIT_MODAL_HINT =
  "Wait ~60 seconds and try again. If it keeps failing, you may have hit the daily quota.";

export const RATE_LIMIT_MODAL_CLOSE = "Got it";
