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
