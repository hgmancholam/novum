# Requirement Understanding — Novum

> Personal interpretation of the Tekton Labs *Full Stack Engineer · Build Challenge*, before any design or code is written.

---

## Amendment 2026-05-27 — "always answer" refactor (ratified)

This document was written before the product constraint *"the agent must always produce a usable response; pure `honest_unanswerable` is not an acceptable terminal"* was ratified. The full rationale and work-package plan live in [research-method-refactor-proposal.md](research-method-refactor-proposal.md). The contract changes below **supersede** the original text wherever they conflict.

| Affected RF | Old contract | New contract (in force) |
|---|---|---|
| **RF-01·E** | Honest stop is a first-class terminal outcome class. | Honest stop is **not** a terminal outcome. The conditions that previously produced it (ambiguity, contradiction, sparsity, out-of-scope type) now drive **`AnswerKind`** selection inside a single `judge_confirmed` terminal. |
| **RF-02** | 7-value `stop_reason` enum. | **4-value** enum: `judge_confirmed`, `stopped_by_budget`, `user_cancelled`, `errored`. The three `honest_*` values are removed. |
| **RF-04** | Honest stop when contradictions cannot be resolved. | Contradictions render as `AnswerKind=weighted` with candidate answers ranked by support strength. |
| **RF-06** | Types 6/7/8 (predictive / opinion / personal-private) emit `honest_unanswerable` immediately. | Types 6/7/8 route to `scenario`, `tradeoff`, and `ethical_redirect` AnswerKinds respectively. **No short-circuit.** The full pipeline runs and a calibrated answer is produced. |
| **RF-12** | `final_confidence = min(S, J)`; threshold gates the positive terminal. | Formula unchanged, **but `S` is multiplied by a per-`AnswerKind` ceiling** before entering the `min`. Failing the threshold **lowers confidence on the answer**, not refuses it. See [confidence-calculation.md](confidence-calculation.md) amendment. |
| **RF-13** | UI surfaces "trust guarantees" including honest-stop screens. | UI surfaces an **`AnswerKind` badge + per-section confidence + alternatives panel**. **No rejection screens.** |
| **RF-17 (new)** | — | Every terminal positive run produces an answer with a declared `AnswerKind` and per-kind-bounded confidence. The six kinds are: `direct`, `weighted`, `scenario`, `tradeoff`, `ethical_redirect`, `best_effort`. |
| **RF-18 (new)** | — | Saturation signal `C` is computed from **in-process** embedding novelty (no pgvector, no DB-side vectors) and emitted as `SaturationDetected`. |
| **RF-19 (new)** | — | The judge LLM role runs on a **different provider** than planner/synthesizer (default: Anthropic Claude Haiku). On provider unavailability, the system degrades gracefully to GitHub Models and emits a `JudgeProviderDegraded` event. See [ai-services.md](../technical-phase/ai-services.md) §1.7. |

**Read-the-doc rule:** wherever the body below mentions `honest_unanswerable`, `honest_contradiction`, `honest_ambiguous`, or any "rejection screen" / "refuses" behavior tied to RF-06, the **amendment above wins**. The original text is preserved for historical context and to make the diff explicit.

---

## 1. The challenge, in one sentence

Build a research agent that, given a question, produces a **sourced answer** and — just as importantly — **decides on its own when it has gathered enough evidence to stop**.

The brief is deliberately open-ended. The evaluators are not looking for *the* right architecture; they want to see **how I frame the problem, which tradeoffs I make, and whether I can defend them under pressure**.

> **Companion documents (understanding phase).** This file is the master RF doc. The following companions go deeper on specific surfaces:
> - [stopping-signal-analysis.md](stopping-signal-analysis.md) — derivation of the A/D/B/E/F layered stopping policy (RF-01).
> - [confidence-calculation.md](confidence-calculation.md) — `min(S, J)` confidence formula and threshold mechanics (RF-12).
> - [ui-prototype.md](ui-prototype.md) — L2 product-intent UI spec: layout, state inventory, component tree, responsive strategy (RF-13).
> - [data-flows-and-diagrams.md](data-flows-and-diagrams.md) — Graphviz visual companion: run sequence, agent FSM, UI run FSM, data-flow layers, plugin seams. Every diagram has a path-coverage check.

---

## Table of contents

- [1. The challenge, in one sentence](#1-the-challenge-in-one-sentence)
- [1-bis. Value framing, target user, and differentiator](#1-bis-value-framing-target-user-and-differentiator)
- [2. What the system must do (the four non-negotiables)](#2-what-the-system-must-do-the-four-non-negotiables) — RF-01 … RF-04
- [2-bis. Self-imposed requirements (not in the brief)](#2-bis-self-imposed-requirements-not-in-the-brief) — RF-05 … RF-16
- [3. What the brief does *not* prescribe (my design surface)](#3-what-the-brief-does-not-prescribe-my-design-surface)
- [4. Deliverables and timing](#4-deliverables-and-timing)
- [5. The review (what I'm being assessed on)](#5-the-review-what-im-being-assessed-on)
- [6. Ground rules (constraints I am operating under)](#6-ground-rules-constraints-i-am-operating-under)
- [6-bis. Success metrics (how I would know it is working in production)](#6-bis-success-metrics-how-i-would-know-it-is-working-in-production)
- [6-ter. Extension surfaces (plugin seams for the pair session)](#6-ter-extension-surfaces-plugin-seams-for-the-pair-session)
- [6-quater. Trust contract with the user](#6-quater-trust-contract-with-the-user)
- [6-quinquies. Roadmap beyond the MVP](#6-quinquies-roadmap-beyond-the-mvp)
- [6-sexies. Risk register (business-level, not just technical)](#6-sexies-risk-register-business-level-not-just-technical)
- [7. Why this challenge exists (reading between the lines)](#7-why-this-challenge-exists-reading-between-the-lines)
- [8. My interpretation of "knows when to stop"](#8-my-interpretation-of-knows-when-to-stop)
- [9. Success criteria I will hold myself to](#9-success-criteria-i-will-hold-myself-to)
- [10. The single thing I am most worried about](#10-the-single-thing-i-am-most-worried-about)

---

## 1-bis. Value framing, target user, and differentiator

> The brief is dressed as an engineering exercise, but it is being graded as a **solutions** exercise. This section frames *why* this system would exist if it were a real product, not just *what* it does.

### The problem worth solving

Knowledge workers — analysts, PMs, technical leads, consultants — burn measurable hours per week on **research questions that need a defensible, sourced answer**: vendor comparisons, technology evaluations, market sizing, policy lookups, due-diligence checks. Existing AI tools fail this job in two predictable ways:

1. **Confidently wrong.** General-purpose chatbots fabricate sources or cite hallucinated ones. The user cannot tell *when* to trust the answer.
2. **Confidently incomplete.** Even citation-aware tools (Perplexity, You.com, Elicit) silently stop when *they* feel done. They do not surface what they did not find, what contradicts what, or why they consider themselves finished.

The cost is not just wasted time — it is **uncalibrated trust**. Decisions get made on shaky evidence because the tool never made its uncertainty legible.

### Who it is for (primary persona)

**"Giovanny" — researcher at Tekton Labs.**
His week is a queue of research questions that need a defensible, sourced answer — technology evaluations, vendor comparisons, client-facing landscape scans. He needs:
- An answer with **citations he can verify**.
- A clear signal of **how confident the system is** and **why**.
- The ability to **redo the research differently** when a colleague or partner questions a conclusion (without starting from scratch).
- A **record** he can hand to a partner, with every step the agent took.

*Demo framing advantage:* by naming a Tekton Labs researcher as the primary persona, the demo positions Novum as a tool **the interviewers themselves would use**, not an abstract product. Every design choice maps to *"would this help Giovanny on Monday morning?"*.

Secondary personas: technical PMs evaluating vendor stacks; founders doing market-landscape scans; internal due-diligence teams at consulting firms.

### Job-to-be-done (one sentence)

> *"Give me a sourced, calibrated answer to this question — and tell me when you cannot."*

### Where Novum is different

| Capability | ChatGPT | Perplexity | Elicit | **Novum** |
|---|---|---|---|---|
| Cites real sources | partial | yes | yes (academic) | **yes** |
| Says when it cannot answer | rarely | rarely | sometimes | **first-class outcome** |
| Surfaces contradictions in sources | no | weak | weak | **first-class event** |
| Inspectable reasoning trace | no | no | no | **yes (Level 3)** |
| Re-runnable from any decision point | no | no | no | **yes (fork)** |
| Trust contract with the user | implicit | implicit | implicit | **documented** |

The wedge is **honest epistemics**, not raw capability. Novum chooses to be the tool you can hand to your boss.

### One-line positioning

> *Novum is a research agent that earns its conclusions — and tells you, on the record, when it cannot.*

---

## 2. What the system must do (the four non-negotiables)

These are the only hard requirements stated in the brief. Everything else is a design decision I own.

1. **Autonomous stopping criterion.**
   The agent must reason about sufficiency of evidence. No hardcoded `max_steps = 5`. The stopping logic has to be **defensible** — I should be able to explain *why* it stopped on any given run.
   *Decision (see [stopping-signal-analysis.md](stopping-signal-analysis.md)):* layered policy with **A · Claim coverage** and **D · Source agreement** as primary gates, **B · LLM-as-judge** as final qualitative confirmer (invoked only when A and D are green), **E · Honest stop** as a first-class terminal outcome reachable from all signals, **C · Saturation** as an input to the judge (not a gate), and **F · Budget** as a clearly-labeled safety net only.

   *Methodological lineage.* The whole policy is an executable adaptation of **Analysis of Competing Hypotheses** (Heuer, *Psychology of Intelligence Analysis*, CIA 1999) for the process and **GRADE** (BMJ working group, 2004–present) for the certainty grading. ACH supplies the *evidence × hypothesis* matrix, the disconfirmation rule (RF-15), and *inconclusive-as-valid-output* (the honest-stop terminals); GRADE supplies the multi-dimensional certainty score with the rating separated from the recommendation (`final_confidence = min(S, J)`). Popper's falsificationism is the philosophical anchor for RF-15; Toulmin's argument model is the atomic data shape of each `EvidenceAdded`. The full criteria, scoring matrix, and rejected alternatives (Toulmin, Bayesian, PRISMA, IRAC, SAFE / FActScore / Reflexion) live in [research-method-selection.md](research-method-selection.md).
   *Concrete provider mapping (planner + judge + synthesizer LLMs):* see [technical-phase/ai-services.md](../technical-phase/ai-services.md).

2. **Full inspectability of completed runs.**
   After a run finishes, anyone (me, a reviewer, a teammate) must be able to see:
   - what the agent did (steps / tool calls),
   - what it found (sources, snippets),
   - what it concluded (the answer),
   - **why it decided to stop**.
   *Decision:* **Level 3 inspectability** — structured run log + navigable trace UI (timeline of steps, evidence linked to source, stop decision highlighted) + **scoped diff viewer between two runs** (three views only: timeline diff, evidence diff, outcome diff). Includes a **"fork from this step" button** that triggers the RF-03 engine. Always-on invariants for every trace:
   - **Read-determinism:** opening the same run twice shows the same thing (no live LLM regeneration).
   - **Citation traceability:** every claim in the final answer points to ≥1 evidence chunk, which points to its original source with capture timestamp.
   - **First-class stop reason:** enum field (`judge_confirmed` | `honest_unanswerable` | `honest_contradiction` | `honest_ambiguous` | `stopped_by_budget` | `user_cancelled` | `errored`), never free text. The judge (RF-01·B) is the only path to a positive terminal; full coverage without a judge ruling is the *precondition* that invokes B, not a terminal of its own.
   - **Atomic snapshot:** a crash mid-run leaves recoverable partial state, never corruption.
   *Scope discipline:* the diff viewer is the **first thing sacrificed** if the build budget tightens; the RF-03 engine takes priority.

3. **Re-examinable and re-attemptable runs.**
   A run is not a black box that only emits a final string. It must be possible to **rewind to an intermediate point and branch a new attempt from there** when an earlier decision turned out to be wrong.
   *Decision:* **event log as source of truth; snapshots deferred to V2.**
   - **Event log** (append-only `events` table in PostgreSQL, with `payload JSONB`) is canonical. Event types: `QuestionAsked`, `PlanCreated`, `ToolCalled`, `EvidenceAdded`, `ClaimCovered`, `ClaimUncoverable`, `ContradictionDetected`, `JudgeRuled`, `Stopped`. Each event carries `id`, `run_id`, `parent_event_id`, `step_index`, `type`, `payload`, `timestamp`. *Technical-phase update: the persistence engine is Postgres (see [technical-phase/architecture.md §5](../technical-phase/architecture.md)) — the original JSONL-on-disk proposal was promoted to a real DB to support indexed run listing (RF-09) and ACID-safe forks (RF-03).*
   - **Snapshots ⏳ V2 — amendment.** The original hybrid model proposed periodic snapshots as a resume cache. The technical phase deferred them to V2: at the realistic scale of this build (~30 events per run), replaying from the indexed `events` table is sub-millisecond, so snapshots add ~100 LOC and a second schema for no measurable benefit. **V1 resume = full event replay from Postgres** (`SELECT ... FROM events WHERE run_id = ? ORDER BY step_index`). Snapshots will be reintroduced in V2 only if profiling on real runs shows replay latency becoming user-visible. The append-only contract and the fork semantics below are unchanged by this amendment.
   - **Branching = copy event prefix `events[0:k]` to a new `run_id` with `parent_event_id` linking to the fork point + continue from there.** No in-place edits to existing events.
   - **Fork granularity: decision points only.** Users can fork only from events that represent a meaningful choice by the agent: `PlanCreated`, `JudgeRuled`, `ContradictionDetected`, `AmbiguityDetected`, and `Stopped` (any terminal state). Mechanical events (`ToolCalled`, `EvidenceAdded`, `ClaimCovered`, `ClaimUncoverable`, `SourceFailed`) are **not** forkable — forking from them would not produce a different reasoning path, only a different sequence of identical work. The UI hides the fork button on non-decision events.
   - **Idempotency:** event payloads contain tool/LLM outputs, so replay reconstructs state without re-calling external services. New branches make new calls only from the fork point onward.
   *Risk:* event schema drift during the build. Mitigation: lock the ~8 event types in the design doc and keep `payload` opaque.

4. **Graceful handling of messy reality.**
   - **Ambiguous questions** → the agent should not silently pick one interpretation.
   - **Contradictory sources** → it must surface the conflict, not paper over it.
   - **Empty / failing sources** → it must keep going (or stop honestly) without pretending nothing happened.
   *Decisions:*
   - **Ambiguity → early honest stop.** When the agent detects ambiguity up front, it emits `honest_ambiguous` with a list of likely interpretations. The user clarifies by **forking the run with a refined question** — the fork *is* the clarification. No mid-run interactive prompts (would break the autonomous-run model).
   - **Contradiction → bounded resolution attempt, then honest stop.** When D (source agreement) detects a real conflict, the agent launches **up to 2 extra dispute-oriented searches** before giving up. If unresolved, emit `honest_contradiction` with all positions and their sources documented in the trace. Never report a majority answer silently.
   - **Source failure → cascading fallback.** On any tool-call failure (0 results, HTTP error, timeout):
     1. **Retry once** (handles transient errors).
     2. **Reformulate the query** with an LLM call and retry once (handles bad queries).
     3. **Switch source** (e.g., web search → Wikipedia) and retry.
     4. **Always log a `SourceFailed` event** with `reason`, `query`, `tool`, `attempt_number`.
     5. If all sources fail for a sub-claim, leave it uncovered; the RF-01 cascade will route this to `honest_unanswerable` or to a `judge_confirmed` answer with explicit caveats.
   - **Minimum source set:** **web search + Wikipedia API** (heterogeneous, ≥2 independent providers). arXiv / HN Algolia optional if budget allows. Heterogeneity is what makes D (source agreement) and the dispute-resolution loop meaningful. *Concrete provider mapping (Tavily for web, `wikipedia-api` for Wikipedia, cost/quotas/rationale): see [technical-phase/ai-services.md](../technical-phase/ai-services.md).*
   *Event-type additions for RF-04:* `SourceFailed`, `AmbiguityDetected`, `ContradictionDetected` (the last one already mentioned in RF-03), plus `ClaimUncoverable` (emitted when all source strategies for a sub-claim are exhausted; the claim is then excluded from coverage signal A's denominator so the run can still close honestly on the remaining claims instead of forcing budget exhaustion). Running event-type count after RF-04: **~11**. Later RFs add `AgentErrored`, `ResumedAfterError`, `ResumedAfterCancel` (see RF-08 and RF-11), then `PlanCritiqued`, `PlanRevised` (RF-14) and `ConfidenceMismatch` (RF-15), bringing the final count to **~17**.

---

## 2-bis. Self-imposed requirements (not in the brief)

These are scope decisions I have taken on top of the brief because they materially improve the demo and the pair-session story. They are mine to defend.

5. **Cross-session persistence with lightweight identity and public runs.**
   A user must be able to **close the session, come back later, find any previous run (their own or someone else's), and fork from any step**. Runs are a shared public commons; the username is an attribution label, not an access boundary.
   *Decision — lightweight identity (no real auth):*
   - **Unique username only.** No password, no email, no passphrase, no recovery flow.
   - **Login = "give me your username; I create your space if it does not exist."** Pure namespace claim.
   - **Persistent token** (opaque random string) stored in `localStorage` as `novum.token`; sent on each request as `Authorization: Bearer <token>` to identify *who is acting*. No cookies (avoids CSRF surface and keeps the cross-origin Vercel ↔ Oracle-VM contract simple).
   - **Logout = delete the token client-side.** Server keeps the data; logging back in with the same username restores attribution.
   *Decision — public-runs model (GitHub-fork semantics):*
   - **Every run is world-readable.** Any logged-in user can open any run and inspect it (trace, evidence, stop reason, diff vs other runs).
   - **Any user can fork any run at any step.** The new run is owned by the forking user, with `parent_run_id` and `forked_at_event_id` linking back to the origin.
   - **Any user can re-ask the same question as a new independent run** (no fork relationship), or **resume their own in-progress runs**.
   - **A user can only mutate runs they own** (i.e., only the original author can resume an in-progress run of theirs; everyone else can only read or fork).
   - **Data layout is flat, not user-scoped:** runs and events live in shared Postgres tables (`runs`, `events`) with `runs.owner_username` as the attribution column. This makes "list all runs" a single indexed `SELECT` and "fork another user's run" a transactional copy of the event prefix.
   *Concurrency:* **single-writer-per-run discipline** — the application enforces one agent `asyncio.Task` per `run_id` (in-process registry; second resume attempts get 409). Postgres MVCC handles concurrent readers. Documented as single-server scope (no distributed locking).
   *Explicit non-goals (called out in the demo so it is never mistaken for production auth):*
   - **No identity verification.** Anyone who knows a username can claim that namespace and act in its name. This is a demo, not a multi-tenant product.
   - **No private runs, no access control, no deletion of others' runs.**
   - **No rate-limit on username claims, no abuse prevention.**
   *Why this and not full auth:* the brief explicitly says polish is not the point, and a real auth stack would eat hours that belong to the agent loop. The public-commons model is also a *feature* for the demo — the reviewer can fork one of my runs live and see the branching engine work on real data.

6. **Explicit scope of supported question types + upfront user disclosure.**
   The system declares which question types it supports and which it does not, both in the agent (so it can `honest_unanswerable` early without wasting tokens) and in the UI (so the user knows before submitting).
   *Decision — supported types:*
   - **Type 1 · Factual / objective** — *"When was Tekton Labs founded?"*
   - **Type 2 · Comparative** — *"React vs Vue for a team of 5."*
   - **Type 3 · Definitional / explanatory** — *"What is event sourcing?"*
   - **Type 4 · State-of-the-art / current practice** — *"Best framework for LLM agents in 2026?"* (expect `judge_confirmed` with caveats or `honest_contradiction`).
   - **Type 5 · Causal / "why"** — *"Why did Rust gain traction in systems programming?"* (same caveats as Type 4).
   *Decision — out of scope (declared, not silently rejected):*
   - **Type 6 · Predictive / future** — *"Will LLMs replace programmers in 5 years?"* → `honest_unanswerable`.
   - **Type 7 · Pure opinion / subjective** — *"What's the best programming language?"* → `honest_unanswerable`.
   - **Type 8 · Personal / private** — *"What's John Doe's home address?"* → `honest_unanswerable` (also ethical out-of-scope).
   *Agent behavior:*
   - A **pre-classification phase** (one cheap LLM call) precedes `PlanCreated`. The detected type is stored in `PlanCreated.payload.question_type` — auditable and diff-able between runs (no new event type needed).
   - If type ∈ {6, 7, 8} → emit `Stopped(honest_unanswerable)` immediately, with the detected type and a one-line explanation. No tokens spent on search.
   - If type ∈ {1..5} → continue to the normal flow.
   - **In case of doubt during classification → default to Type 1 (factual)** and let the engine operate. Better to over-process than to bounce a legitimate question during the live demo.
   *UI disclosure (mandatory):*
   - The question-input screen shows, **before the user types**, a short panel listing the five supported types with one example each, and the three unsupported types with the reason. No dialog modal, no "learn more" link buried two clicks deep — visible by default.
   - When a question is rejected as out-of-scope, the rejection screen quotes the exact unsupported-type definition the system matched, so the user understands *why* and can reformulate.
   *Why this matters:* it converts "the agent refused to answer" from a perceived bug into a documented, defensible feature. Knowing what it should *not* answer is part of "knowing when to stop."

7. **Optional user-provided context (background notes, not evidence).**
   On the question-input screen, the user can optionally paste a short paragraph of context — what they already know, constraints, or hints about intent — alongside the question.
   *Decision — context is guidance, not truth:*
   - **Stored in `run metadata` as `user_context`**, cap **1000 characters**. Visible at the top of the trace (collapsible section).
   - **Injected only in two places:** the question-type classifier (RF-06) and the planner. **NOT** injected in the judge (B) or in the final-answer synthesizer — protects against unverified user claims poisoning the evaluation or the citations.
   - **Never treated as a source.** Does not contribute to claim coverage (A), does not participate in source agreement (D), is never cited in the final answer.
   - **Contradiction handling:** if a retrieved source contradicts something asserted in `user_context`, the engine emits a `UserContextChallenged` event (new optional event type) and the final answer surfaces it as a caveat *("your assumption that X appears unsupported by the sources, which indicate Y")*. The agent respects the user but does not lie to them.
   - **Fork inheritance:** when forking another user's run, `user_context` is pre-filled with the original value but **editable** by the forker.
   - **Empty by default** — never required, so the demo with reviewer-supplied questions works with zero friction.
   *Why this and not C (context-as-source):* keeping user input out of the evidence base preserves the integrity of A/D/B. The agent's reasoning remains grounded in verifiable retrievals; the user's input only *guides* exploration. This is also the boundary that lets the demo defend "the agent will not confidently cite something just because you told it to."

8. **Live streaming of the run + cancellation.**
   While a run is in progress, the user sees the trace **build live**: events appear in the timeline as the agent emits them. No "wait and reveal" spinner.
   *Decision:*
   - **Transport:** Server-Sent Events (SSE) from the agent loop to the browser. Simpler than WebSockets, one-way fits the use case, survives reconnects naturally.
   - **What streams:** every event from the event log, in append order. The UI renders them with the same components used for the post-run trace, so live view and post-run view are visually identical.
   - **Reconnection:** if the SSE drops mid-run, the client reconnects and resumes from the last received `event.id`. Events are idempotent by id.
   - **Cancellation:** the run owner sees a **Cancel** button while the run is in progress. Cancel emits a terminal `Stopped(user_cancelled)` event. The run remains inspectable and forkable like any other; the partial evidence and partial coverage are preserved in the trace.
   - **Resume after cancel:** the run owner sees a **Resume** button on `user_cancelled` runs (symmetric with the Resume offered on `errored` runs — see RF-11). It uses the event log to reconstruct state up to the last event before `Stopped(user_cancelled)`, then continues from there. The append-only contract is preserved: the `Stopped(user_cancelled)` event is followed by a `ResumedAfterCancel(reason: "user_changed_mind")` event so the trace remains complete and auditable. The user explicitly stopping and then changing their mind is a legitimate, common case; making it irreversible would be hostile design.
   - **Non-owners cannot Cancel or Resume**, but they can **fork** a cancelled run from any decision point.
   - **Non-owner viewers** of an in-progress run see the same live stream (read-only) but no Cancel button.

9. **Run discovery (URL + recent runs list).**
   For public runs to be useful, users need a way to find runs to inspect or fork.
   *Decision:*
   - **Direct URL** (`/runs/<run_id>`) deep-links to any run — inspectable by anyone, forkable by anyone logged in. Required for sharing in the demo ("open this link and try forking it").
   - **Home shows a "Recent runs" list**, ordered by `started_at` descending. Each row: question (truncated), owner username, status badge (running / done / errored / cancelled), stop reason, started-at timestamp, fork count.
   - **No full-text search** in this iteration. Documented non-goal; the recent list + URL covers the demo path.
   - **Pagination:** simple "load more" or page-size cap of 50. No infinite scroll.

10. **User-selectable answer format.**
    When submitting a question (and editable later from the run view), the user picks how the final answer is rendered.
    *Decision — two formats, user chooses:*
    - **Format C1 · Prose with inline citations.** Single coherent paragraph(s) with `[1] [2]` markers, followed by the source list. Best for narrative/explanatory questions.
    - **Format C2 · Structured report.** Sections: **TL;DR** (1–2 lines) → **Body** → **Claims table** (each claim with supporting sources) → **Caveats** (contradictions surfaced, low-confidence areas) → **Confidence** (high/medium/low) → **Stop reason**. Best for factual/comparative questions and for the demo — it visibly maps onto the RF-01 stopping logic.
    *Implementation:*
    - Format is stored in `run metadata` as `output_format: "prose" | "structured"`. Default = `structured` (better demo).
    - The final-answer synthesizer is invoked with the chosen format as a parameter; both formats consume the **same** underlying claim+evidence state, so switching format does not re-run research.
    - **Switching format on an existing completed run re-renders the answer without re-running the agent.** Cheap and instant. Diff viewer treats `output_format` as a metadata-only difference, not a trace difference.

11. **Agent-side error handling and recoverable failures.**
    Distinct from tool/source failures (RF-04) and budget exhaustion (RF-01·F): when the LLM provider itself fails (rate limit, 5xx, network timeout unrelated to a source tool), the run must fail visibly and recoverably.
    *Decision:*
    - **Retry policy:** 1 automatic retry with exponential backoff on transient LLM failures. If the second attempt fails → emit terminal `Stopped(errored)` with payload describing the failure mode (`rate_limit` | `provider_5xx` | `provider_timeout` | `unknown`).
    - **New event types:** `AgentErrored(reason, last_attempt_id, retriable: bool)`, `ResumedAfterError(resumed_from_event_id)`, and (from RF-08) `ResumedAfterCancel(reason: "user_changed_mind", resumed_from_event_id)`. Final V1 event-type count (including RF-14 and RF-15): **~17**.
    - **`errored` is a distinct stop_reason** — not conflated with `stopped_by_budget` (our decision) nor with honest stops (the agent's reasoning).
    - **Resume from last good state:** the run owner sees a **Resume** button on `errored` runs *and* on `user_cancelled` runs (see RF-08). It uses the event log to reconstruct state up to the last event before the terminal `AgentErrored` / `Stopped(user_cancelled)` event, then continues from there. This is mechanically the same as forking, except it stays on the same `run_id` (append-only — a `ResumedAfterError` or `ResumedAfterCancel` event is appended so the trace remains complete and auditable). Resuming on the same `run_id` instead of forking preserves the URL and the run's identity in history, which matters for shared links.
    - **Non-owners cannot Resume**, but they can **fork** the errored or cancelled run from the last decision point if they want to try.

12. **User-set confidence threshold per question.**
    Each question carries a **minimum confidence threshold** that the judge (B) must meet before the run can terminate as `judge_confirmed`. Lets the user dial up rigor for high-stakes questions or down for quick lookups.
    *Confidence calculation method:* fully specified in [confidence-calculation.md](confidence-calculation.md). Short version: `final_confidence = min(S, J)` where `S` is a deterministic structural score over claim coverage, source agreement, source diversity, and absence of unresolved conflict; `J` is the adversarially-prompted judge's self-reported confidence. The `min()` aggregation prevents either side from rubber-stamping the other.
    *Decision — mechanics:*
    - **Stored in `run metadata` as `confidence_threshold: float`** in `[0.0, 1.0]`. Default = **0.6** (moderate). UI exposes a 3-position selector (`Low 0.4` / `Standard 0.6` / `High 0.85`) plus an advanced free-input field.
    - **Interaction with RF-01:**
      - The judge (B) already returns `{ sufficient: bool, confidence: 0..1, ... }`.
      - **Stop only if `sufficient == true` AND `confidence >= threshold`.** If sufficient but below threshold, the agent **keeps searching** — the threshold raises the bar, it does not silence the judge.
      - If the run exhausts budget (F) without ever crossing the threshold, terminal is `honest_unanswerable` with payload `{ sub_reason: "confidence_below_threshold", best_confidence: X, threshold: Y }`. This is a **new structured payload, not a new stop_reason** — the enum stays at 7 values.
      - **Judge anti-cycle guard.** If the judge keeps returning `sufficient=false` with `gaps[]` that cannot be filled (the searcher runs out of new evidence, or the same gaps reappear), `RunState.judge_rejections` counts the rejections. When it reaches `max_judge_rejections` (default 3), the run terminates as `honest_unanswerable` with payload `{ sub_reason: "judge_loop_stalled", judge_rejections: N, last_gaps: [...] }`. Same stop_reason as above, different sub_reason — the enum still stays at 7 values. This prevents the search loop from burning the whole budget on a judge that cannot be satisfied.
      - Honest stops by ambiguity or contradiction (RF-04) are **not** gated by the threshold — those are categorical, not confidence-based.
    *UI:*
    - **Question-input screen:** selector visible alongside the format selector (RF-10). Tooltip explains *"higher threshold = the agent searches longer and may stop honestly more often."*
    - **Trace UI:** threshold visible in the run header next to format and stop reason. Diff viewer treats it as a metadata difference.
    *Fork inheritance:* pre-filled from the parent run, **editable by the forker**. This is exactly the *"same question, different threshold"* demo move — the user forks a `honest_unanswerable_low_confidence` run with a lower threshold and watches it resolve, or forks a `judge_confirmed` run with a higher threshold and watches it become honest.
    *Why V1 and not V2:* the judge already produces a confidence number; gating on it is a 5-line policy change. The narrative leverage in the demo (*"watch the same question behave differently at different rigor levels"*) is disproportionate to the implementation cost.

13. **UI as the surface of the trust contract.**
    The brief says polish is not graded, but the **trust contract** of §6-quater is only believable if a user can *see* it: the live trace, the stop reason, the citations, the fork point, the resume button. The UI is therefore treated as a first-class deliverable, not as decoration. The complete L2 product-intent prototype — layout, state inventory, atomic-design component tree, microcopy, technical UI decisions (TanStack Query, SSE protocol, localStorage persistence, responsive strategy), non-goals — is specified in [ui-prototype.md](ui-prototype.md).
    *Decision — V1 scope (full spec in [ui-prototype.md](ui-prototype.md)):*
    - **Stack:** React 19 + Vite + TypeScript strict, Tailwind v4, shadcn/ui (Radix), Motion, Zustand, TanStack Query. *Full library list, versions, and rationale: [technical-phase/tech-stack.md](../technical-phase/tech-stack.md).*
    - **Architecture:** atomic design (atoms → molecules → organisms → templates → pages) enforced via ESLint `import/no-restricted-paths`. Data fetching only at the page layer.
    - **Layout:** 3-panel (history / center / trace) at desktop, **responsive** down to mobile via drawer sheets — 3 breakpoints (`mobile < 768 px`, `tablet 768–1023 px`, `desktop ≥ 1024 px`) with 44 × 44 px touch targets at non-desktop.
    - **State model:** every screen has a deterministic id (L1–L7 history · C1–C13 center · T1a–T5 trace · M1 modals). Each id maps to acceptance criteria and to one or more functional requirements (RF-coverage matrix in §5 of the UI doc).
    - **Trust-contract surfaces:** `TrustSummary` organism at the top of every terminal-state body, `OutcomeBar` atom for pre-attentive outcome recognition, `ConfidenceMeter` for the RF-12 threshold story, `ForkContextCard` showing what the user is forking from, `PlanPreview` before the first event arrives, `ShareLinkButton` for the demo *"open this URL and fork it"* move.
    - **Persistence:** `localStorage` only (`novum.token`, `novum.username`, plus two UI preferences). No cookies. Honors RF-05's lightweight-identity contract.
    - **SSE protocol:** stream-until-`Stopped`, server closes cleanly, `Last-Event-ID` reconnect, 15 s heartbeat, exponential backoff 1 → 2 → 4 → 8 → 16 s max 5 attempts. Implements RF-08.
    *Why V1 and not V2:* the UI is the place where every previous RF becomes legible to a reviewer in a 35-minute demo. Without it, RF-02 (inspectability), RF-04 (contradictions surfaced), RF-08 (live streaming), RF-11 (recoverable failures), and RF-12 (threshold dial) are claims with no surface. The UI is the contract slide rendered as software.

14. **Plan-quality gate and iterative re-planning.**
    The planner is the single biggest leverage point in the whole pipeline — a bad sub-claim decomposition invalidates every structural signal downstream. RF-14 closes that gap with two mechanisms.
    *Decision — plan critic before search (1.4):*
    - **One LLM call** immediately after `PlanCreated` runs a structured critic over the plan: `plan_critic(question, sub_claims) → { covers_intent: bool, granularity_ok: bool, mutually_exclusive: bool, issues: [...], reasoning: str }`. The verdict is persisted as a new event `PlanCritiqued(approved, issues, reasoning)`.
    - If `approved == false`, the planner is invoked **once more** with the critic's `issues` as feedback; the new plan is critiqued again.
    - If the second plan also fails, the run terminates as `Stopped(honest_ambiguous, sub_reason="plan_unstable", issues=[...])`. **Same `stop_reason` enum, new sub_reason** — the enum stays at 8 values (the count in the design doc).
    - If `approved == true` at any pass, the run proceeds to `Searching`.
    *Decision — iterative re-plan during search (2.1):*
    - The planner can emit `PlanRevised(parent_plan_event_id, added[], removed[], modified[], reasoning)` at most **`max_replans` times per run** (default 2). Triggers:
      - the judge (B) returns `gaps[]` that look like missing sub-claims rather than missing evidence (heuristic: a gap that is not satisfied by any existing sub-claim);
      - a `ConfidenceMismatch` (RF-15) of type `S_low_J_high` persists across two judging passes;
      - the dispute-resolution loop (RF-04) exhausts its 2-attempt cap **and** the conflict is structural (different sub-claims interpret the question differently).
    - `PlanRevised` is **append-only**. The denominator of `C_coverage` and `C_no_conflict` (see [confidence-calculation.md](confidence-calculation.md)) recomputes against the **current** plan = `PlanCreated ∪ Σ PlanRevised`. Evidence already bound to a removed claim is preserved (read-only) for audit, but does not count toward coverage.
    *FSM impact:* one new state `Replanning` reachable from `Planning` (after `PlanCritiqued.approved=false`) and from `Searching` (when a re-plan trigger fires). Returns to `Searching` on `PlanRevised`, or to `StoppedHonestAmbiguous` if `max_replans` is exhausted with the trigger still active.
    *Event-type additions for RF-14:* `PlanCritiqued`, `PlanRevised`. Running event-type count after RF-14: **~16**.
    *Why V1:* the structural confidence score `S` is only as meaningful as the plan it scores. Without a plan critic, *"the agent decomposed the question wrong"* is an unrecoverable silent failure mode. ~40 LOC closes it.

15. **Disconfirmation pass, source independence, and confidence-mismatch trust-flag.**
    Three small mechanisms that together convert the agent from *"collector of confirming evidence"* into *"investigator that knows what it cannot tell."* All three are detailed in [confidence-calculation.md](confidence-calculation.md); RF-15 is the requirement-level contract.
    *Decision — disconfirmation pass (1.1):*
    - **For every claim** that reaches `C_coverage(c) ≥ N_min`, the searcher issues **one additional adversarial query** before the claim is considered ready for the judge: `query_anti = LLM("reformulate this claim so that a search would return evidence that contradicts or limits it")`.
    - Each `EvidenceAdded` event carries a new field `polarity ∈ { "supporting", "refuting", "limiting" }` set at extraction time by the planner/extractor. Default polarity is `supporting`; the disconfirmation pass biases retrieval toward `refuting` / `limiting`.
    - Refuting and limiting evidence **form their own cluster** in the `C_agreement` calculation, so genuine disconfirmation lowers agreement (correctly) instead of being silently averaged in.
    - The disconfirmation query is **a `ToolCalled` event** with `payload.query_intent = "refuting"`, so the trace shows the agent actively looked for counter-evidence. No new tool, no new source.
    *Decision — source independence metric (1.3):*
    - The diversity term `C_diversity` becomes a blend of **source-kind diversity** (the original V1 metric) and **domain independence** (new): `C_independence = |distinct_etld+1_domains| / |evidence_chunks|`, both in `[0, 1]`.
    - Final term: `C_diversity = 0.5 · diversity_kinds + 0.5 · C_independence`. Five blog posts on `medium.com` now count as one effective source, not five.
    - **No weight change** to the overall confidence formula (`C_coverage 0.35 / C_agreement 0.30 / C_diversity 0.20 / C_no_conflict 0.15`) — only the internal composition of the diversity term.
    *Decision — confidence-mismatch trust-flag (1.2):*
    - After every `JudgeRuled`, the engine computes `|S − J|`. If it exceeds **0.3**, emit `ConfidenceMismatch(S, J, delta, regime)` where `regime ∈ { "S_high_J_low", "S_low_J_high" }`.
    - The event **does not block** the run. It is a trust-flag surfaced in the UI inside `TrustSummary`:
      - `S_high_J_low` → *"the evidence looks structurally complete but the judge sees something subtle"* → continue searching is correct.
      - `S_low_J_high` → *"the judge is confident on thin evidence"* → **alarm**: feeds RF-14's `PlanRevised` trigger and is shown to the user as a yellow flag even on `judge_confirmed` terminals.
    - The trust contract (§6-quater) is amended: *"if the structural score and the judge ever disagree by more than 0.3, you will see it in the trace."*
    *Event-type additions for RF-15:* `ConfidenceMismatch`. `EvidenceAdded` gains `polarity`; `ToolCalled` gains `query_intent`. Schema evolution stays inside the `extra="allow"` contract (RF-02). Running event-type count after RF-15: **~17**.
    *Why V1:* disconfirmation is **the** methodologically defensible move — it operationalizes falsification, not collection. Independence closes the echo-chamber grietas listed in R3. The mismatch flag turns the conservative `min(S, J)` from a silent gate into legible information. Combined cost: ~60 LOC.

16. **Minimal calibration eval set and reproducible run grading.**
    Confidence weights `(0.35, 0.30, 0.20, 0.15)` are documented as intuition (see [confidence-calculation.md §6](confidence-calculation.md)). RF-16 commits to a **5-question hand-labeled eval set** for V1 — small enough to run by hand, large enough to move the conversation from *"these weights are my intuition"* to *"these weights survived 5 labeled cases."*
    *Decision:*
    - **Five questions, one per type** that V1 supports: factual, comparative, definitional, SotA, causal. Each labeled with the expected `stop_reason` enum value and a one-line rubric.
    - Stored as a fixture under `backend/tests/fixtures/eval/v1_seed.yaml` and replayable via a `make eval` target that runs the agent, collects `JudgeRuled.payload` and `Stopped.payload` into a CSV, and prints a delta against the labels.
    - The eval set is **not** the calibration itself — V2 calibration requires ~50 questions (see [confidence-calculation.md §6](confidence-calculation.md)). V1's job is to **prove the wiring works and the weights are not pathological** on a non-trivial set.
    - Run on every commit that touches `app/agent/`, `app/seams/signals/`, or `app/llm/`. CI-light: skipped if `GITHUB_TOKEN` is absent.
    *Why V1:* converts the calibration debt from a hand-wave into a measurable artifact. In the demo, *"here is the eval CSV from this morning's run"* is the kind of empirical honesty that distinguishes seniority. Cost: 1 h of labeling + 20 LOC of script.

---

## 3. What the brief does *not* prescribe (my design surface)

Everything below is **my choice** — and every choice must be justifiable in the pair session:

- Language, framework, runtime.
- LLM provider(s) and model(s).
- Data store (relational, document, vector, plain files…).
- Search / retrieval tools (web search API, scrapers, local corpus, RAG…).
- Agent loop shape (single-agent ReAct, planner+executor, graph, state machine…).
- How "enough evidence" is operationalized (confidence score, claim coverage, source agreement, budget-aware stop, …).
- How runs are persisted and replayed (event log, snapshots, tree of states…).
- UI / interface (CLI, web, notebook). Polish is explicitly *not* the point.

---

## 4. Deliverables and timing

| # | Artifact | Deadline | What it contains |
|---|----------|----------|------------------|
| 1 | **Design doc** | 24 h from receiving the challenge | One page. Architecture, data model, **how the system decides to stop**, and the **single thing I am most worried about**. In my own voice — not LLM-generated prose. |
| 2 | **Working build** | Within one week of the design doc | Running system + source code + a short delta note on what changed from the design doc and *why*. |

Recommended effort on the build itself: **4–6 focused hours**. Polish is not evaluated; clarity of thought is.

---

## 5. The review (what I'm being assessed on)

A 35-minute conversation, after both artifacts are submitted:

- **00–15 min · Demo.** The interviewers bring **three research questions of their own**. I run them live against my system and narrate what happens — including the stopping decision on each.
- **15–35 min · Pair session.** They introduce a **new requirement not in the brief**, and we extend the system together.

Implications for me:
- The system must be **runnable on demand, reproducibly**, on whatever machine I bring.
- Inspectability is not a nice-to-have — it is the *substrate* of the demo. I need to be able to point at *why* the agent stopped, on questions I have never seen before.
- The architecture must be **extensible under time pressure**. If a clean seam exists for "add a new tool / new evaluator / new stopping signal", the pair session will go well. If everything is hardwired, it won't.

---

## 6. Ground rules (constraints I am operating under)

- **Stack:** entirely free choice.
- **AI assistance:** allowed and expected — but I must be able to defend every line and every decision as my own.
- **Time:** 4–6 hours on the build; one-week hard wall.
- **Polish:** not graded. **Muddled reasoning is the failure mode**, not rough edges.

---

## 6-bis. Success metrics (how I would know it is working in production)

These are the KPIs I would actually report to a stakeholder. Not all are measurable inside a 4–6 h build, but every one is **defendable**.

| # | Metric | Why it matters | Target (illustrative) |
|---|---|---|---|
| 1 | **Appropriate-honest-stop rate** | % of unanswerable/ambiguous/contradictory questions where the agent correctly emitted an `honest_*` stop instead of forcing an answer. The single best proxy for whether the brief was solved. | ≥ 80% on a labeled eval set |
| 2 | **Citation grounding rate** | % of claims in the final answer that have ≥1 supporting evidence chunk traceable to a real source. Detects hallucinated citations. | 100% (any miss is a bug) |
| 3 | **Median time-to-answer** | Wall-clock from `QuestionAsked` to terminal `Stopped`. Drives demo feel and unit economics. | < 45 s for Type 1–3, < 90 s for Type 4–5 |
| 4 | **Cost per run** | Average $ in LLM + search API per completed run. Scales with token usage of the judge (B) and the planner. | < $0.10 for Type 1–3 |
| 5 | **Fork value-add rate** | % of forks whose terminal `stop_reason` or final answer **differs** from the parent. Validates that branching is a real feature, not a vanity button. | ≥ 40% |
| 6 | **Source-agreement rate by question type** | Average D-score per type. Surfaces which question types Novum handles cleanly vs needs more sources. | Type 1: ≥ 0.8; Type 4–5: ≥ 0.5 |
| 7 | **Cancellation / abandonment rate** | % of runs ending in `user_cancelled` before terminal. Proxy for bad UX (too slow, going nowhere). | < 5% |
| 8 | **Resume success rate** | % of `errored` runs that the owner successfully resumes to a non-errored terminal. Validates that the event log is truly recoverable. | ≥ 90% |

**What I will actually report in the demo:** metrics 1, 2, 3, 5 — the ones I can compute from the three demo runs in real time.

---

## 6-ter. Extension surfaces (plugin seams for the pair session)

The pair session will ask me to add something not in the brief. I am pre-committing to three extension seams so the answer is *"that lives in seam X; here is how it slots in"*, not improvisation.

### Seam 1 · Source plugin

Adding a new source of evidence (Confluence, arXiv, a customer's PDF corpus, a SQL database).

```
interface Source {
  name: string                                  // unique id, used in events
  search(query: string, k: int): Evidence[]     // returns ranked snippets
  health_check(): { ok: bool, latency_ms: int } // for failure cascade in RF-04
  metadata: { kind, citation_template, ... }
}
```

Registered in a central `source_registry`. The planner discovers available sources at run start and decides which to query per sub-claim. **Adding a source is one file + one registry line, no changes to the loop.**

### Seam 2 · Stopping-signal plugin

Adding or replacing a stopping signal (e.g., "add a domain-specific safety evaluator that blocks stop on medical-advice questions until a disclaimer is attached").

```
interface StoppingSignal {
  name: string
  evaluate(state: RunState): { vote: "stop" | "continue" | "block", reason: string, payload }
}
```

The layered policy from RF-01 (A, D, B, E, F) is itself implemented as five plugins implementing this interface. Adding a sixth signal is registering it with a priority. **The pair session's likely "add a new stopping rule" is a 1-file change.**

### Seam 3 · Output-format plugin

Adding a new way to render the final answer (PDF report, JSON for an API consumer, executive-brief markdown, Slack-friendly summary).

```
interface OutputRenderer {
  name: string                                  // also the value of run.output_format
  render(state: RunState): RenderedOutput       // string | bytes | mime-typed payload
}
```

The two formats from RF-10 (`prose`, `structured`) are two plugins. Adding `pdf` or `json` is registering a third. **Switching format on a finished run re-invokes only this plugin — no agent re-run.**

### Seams I am explicitly *not* committing to

- A **planner plugin**. The planner is the brain; making it swappable is V2 work.
- A **storage plugin**. PostgreSQL via SQLAlchemy + Alembic is the V1 backing store; swapping to another engine would be a single repository-module rewrite, not a plugin contract.
- A **provider plugin** for LLMs. Already abstracted behind a thin `llm.call(prompt, ...)` wrapper — not promoted to plugin status because the contract is too thin to be useful as a documented seam.

---

## 6-quater. Trust contract with the user

What Novum **guarantees**, what it **does not**, in plain language. This is the first slide I would show a client.

### Guarantees

- **No invented sources.** Every citation points to a real URL captured at a real timestamp.
- **Every claim is grounded.** No claim in the final answer exists without ≥1 evidence chunk pointing at a source.
- **The stop reason is honest.** It is an enum chosen by the engine, not free-text rationalization. If we stopped because we ran out of budget, the answer says `stopped_by_budget`, not "here is your answer."
- **Contradictions are surfaced, not hidden.** If sources disagree and we cannot resolve it, you will see it.
- **Every run is fully replayable.** You can audit any step, any tool call, any LLM output that produced any conclusion.
- **No silent retries.** Failures of sources or of the agent itself are visible events in the trace.

### Non-guarantees (explicitly out of scope)

- **Source correctness.** If every source on the web says X and X is wrong, Novum will say X. Mitigation is heterogeneous sources and the dispute-resolution loop, not omniscience.
- **Answers in opinion, prediction, or personal-data domains** (Types 6–8, see RF-06). The system will honest-stop.
- **Privacy.** Every run is public. Do not paste confidential information into questions or `user_context`.
- **User-isolation auth.** Anyone can act as any username. This is a demo namespace, not a tenancy boundary.
- **High-stakes domain safety.** Medical, legal, financial advice is not blocked, but the system makes no claim of fitness for those domains. A real deployment would need a domain-safety stopping signal (seam 2).
- **High availability.** Single-server PostgreSQL persistence. Not a production-grade SLA.

### Why this contract is the right slide

A Solutions Director gets paid to **say no to the right things in writing**. This contract is the artifact of that discipline — it converts "the agent refused to answer" or "two users saw each other's data" from a perceived bug into a deliberate, defensible design choice.

---

## 6-quinquies. Roadmap beyond the MVP

The build is V1. Calling out V2 and V3 in writing signals product thinking and pre-loads the answer to *"how would you grow this?"*.

### V1 · This build (4–6 h focused effort)

- Single-server, PostgreSQL persistence, public commons.
- **Lightweight identity** (username + persistent token, no password — see RF-05).
- 2 sources (web + Wikipedia), 1 LLM provider, layered stopping policy, fork from decision points.
- Live SSE streaming, Level-3 inspectability with diff viewer.
- Two output formats (prose, structured).
- **User-set confidence threshold per question** (see RF-12) — a high-stakes-friendly capability shipped in V1 because it costs almost nothing on top of the judge (B) and dramatically widens the demo narrative (*"I asked the same question with threshold 0.5 and 0.9; here is how the agent behaved differently."*).

### V2 · Productization (4–8 weeks of real engineering)

- **Private workspaces and team accounts.** Real auth, role-based access (viewer / runner / admin), private vs public runs.
- **Custom sources per workspace.** Confluence, Notion, file/PDF upload, SQL connector. Implemented as Seam 1 plugins.
- **Exportable reports.** PDF / Word / Notion-page rendering as a Seam 3 plugin.
- **Persistent storage in a real DB** (Postgres + object store for raw evidence) behind the same event-log abstraction.
- **Observability dashboard** for the KPIs above.

### V3 · Platform (quarter-scale roadmap)

- **Public API** for embedding Novum into other products.
- **Integrations:** Slack/Teams bots, Chrome extension, IDE extensions.
- **Domain-specific evaluator packs:** medical, legal, financial — each adds Seam 2 stopping signals and Seam 1 curated sources.
- **Multi-language** question + source support.
- **Org-level analytics:** which questions does my team ask, where does Novum honest-stop most, where do we need better sources.
- **Fine-tuned classifier** for the RF-06 question typing, trained on real usage.

---

## 6-sexies. Risk register (business-level, not just technical)

Risks a Solutions Director must have thought about — even if not mitigated in V1.

| # | Risk | Likelihood | Impact | V1 mitigation | V2+ mitigation |
|---|---|---|---|---|---|
| R1 | **Hallucination liability in high-stakes domains** (medical/legal/financial) | medium | high | Out-of-scope disclosure in the trust contract; no domain-safety blocker yet. | Domain-specific stopping signal (Seam 2) that blocks stop without a disclaimer. |
| R2 | **Source bias** (English-language web, Western-centric) | high | medium | Documented as a non-guarantee. | Multi-language sources, curated regional source packs. |
| R3 | **Echo-chamber failure** (all sources agree and all are wrong) | medium | medium | Heterogeneous sources + adversarial judge prompt. | Cross-domain source pools (academic + news + primary docs). |
| R4 | **Cost blowup** from abusive or runaway runs | medium | medium | Budget cap (RF-01·F) + cancellation. | Per-user rate-limits, daily token quotas. |
| R5 | **LLM vendor lock-in or outage** | medium | high | Thin `llm.call` abstraction; provider name in run metadata. | Multi-provider with automatic failover, evaluator on a different provider than the synthesizer (also helps R6). |
| R6 | **Judge sycophancy** (B agrees with itself) | medium | medium | Adversarial prompt + judge on different model family than synthesizer (planned, see stack section). | Two-judge disagreement requirement; periodic offline calibration eval. |
| R7 | **Prompt injection via `user_context` or source content** | medium | medium | 1000-char cap on user_context; user_context not injected in judge/synthesizer; source content sanitized at ingestion. | Structured tool-call boundaries, allow-listed instruction surfaces. |
| R8 | **Data durability** (single-server Postgres) | low | high | Append-only event table + daily `pg_dump` to `/backup`; documented as single-server scope. | Managed Postgres (Neon/RDS) + off-host object-store backups, multi-region in V3. |
| R9 | **Public-runs misuse** (someone runs offensive/PII questions under a claimed username) | medium | medium | Question-type classifier rejects personal-data (Type 8); demo-scope disclosure. | Real auth + moderation in V2. |
| R10 | **Demo-time external dependency outage** (search API down during the demo) | low | high | Wikipedia as fallback source; pre-warmed cache for likely demo questions; offline-mode toggle for the day-of demo. | Multi-provider source pool. |

**The one that scares me most:** R6 (judge sycophancy). It is the failure mode where the system *looks* fine and is silently broken — hardest to demo around, easiest to lose credibility on if pushed.

---

## 7. Why this challenge exists (reading between the lines)

The brief itself compares this to the classic "shuffle a deck, draw the top card, count shuffles until the same card reappears" full-stack exercise: a single unit of work that has to travel cleanly through *every* architectural boundary, so you cannot fake any of them.

Translated to this challenge, the "single unit of work" is **one research question**, and the boundaries it has to cross are:

- input handling and disambiguation,
- planning / tool selection,
- evidence gathering and storage,
- conflict and gap detection,
- the **stopping decision** (the heart of the exercise),
- answer synthesis with citations,
- persistence of the full trace,
- replay / branching from an earlier state.

If any of those boundaries is glossed over, the demo will expose it.

---

## 8. My interpretation of "knows when to stop"

This is the load-bearing phrase of the entire brief, and I read it as **three things at once**:

1. **Epistemic stop** — the agent has enough corroborated evidence to answer with calibrated confidence (and can say so).
2. **Pragmatic stop** — additional searches are unlikely to change the answer (diminishing returns / budget awareness), and the agent recognizes that.
3. **Honest stop** — if the question is unanswerable, contradictory, or under-specified, the agent stops and **says that**, instead of hallucinating closure.

A system that only implements (1) is naive. A system that implements all three is what I believe is actually being asked for.

---

## 9. Success criteria I will hold myself to

- On any of the three unseen questions in the demo, I can point at the trace and explain, in one sentence, **why the agent stopped where it did**.
- During the pair session, adding the new requirement is a **localized change**, not a rewrite.
- The design doc I send at 24 h matches the system I demo at one week — or every deviation is explicitly called out and justified.
- The agent never produces a confident answer it cannot cite, and never hides a contradiction it actually saw.

---

## 10. The single thing I am most worried about

**Making the stopping criterion principled rather than vibes-based**, while keeping it cheap enough to run inside a 4–6 hour build and fast enough to demo live.
