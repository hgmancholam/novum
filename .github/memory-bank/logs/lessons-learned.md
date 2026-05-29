# Lessons Learned

> Repository of lessons learned during the Novum development.
> All agents must consult this before starting tasks and update after completing them.

**Last Updated:** 2026-05-28
**Total Lessons:** 31

> **Reaffirmed 2026-05-26:** L-002 (mandatory unit tests, backend + frontend) is an active, non-negotiable rule. See D-006 in `decisions-history.md`.
> **Reaffirmed 2026-05-26:** L-008 (mandatory API_URL prefix) is an active, non-negotiable rule for ALL frontend API calls.
> **Reaffirmed 2026-05-29:** L-018 (Slate Aurora is MANDATORY for every screen) — see `docs/understanding-phase/ui-design.md` §0 preamble + §11 Pattern lock-in, and D-AURORA-MANDATORY.

---

## Recent Lessons

## L-031: `role="status"` is not allowed on `<footer>` (axe `aria-allowed-role`) (2026-05-28, IP-27)
**Context:** `ServiceStatusBar` is a `<footer>`. Adding `role="status"` to make it a live region tripped axe (`aria-allowed-role`): the implicit role of `<footer>` is `contentinfo`, and `status` is not in its allowed-role list.
**Fix:** drop `role="status"`. The `aria-live="polite"` attribute alone establishes live-region semantics without overriding the element's implicit role. Add `aria-label` for an accessible name.
**Rule of thumb:** before adding `role=` to a semantic landmark element (`<header>`, `<footer>`, `<nav>`, `<main>`, `<aside>`), check whether ARIA actually allows that role on that element. For live regions on a landmark, prefer `aria-live` over an explicit `role`.

## L-030: "Test hang" is often a real network call under tenacity backoff (2026-05-28, IP-26)
**Context:** `tests/test_agent_orchestrator.py` looked like it hung at session-fixture setup. The summary inherited the diagnosis "fixture hang" from a previous session. Reality: the orchestrator drives `embed()` (via saturation signal + planner similarity pass), which dials litellm → OpenAI 401 (stale `.env.test` key) → GitHub token-pool fallback → rate-limited → tenacity retries with exponential backoff. Looked like a hang, was actually slow real I/O.
**Diagnostic recipe (in this order):**
1. Run with `-v -s -x` so stdout is unbuffered and shows the last line before the supposed hang.
2. Pipe through `Tee-Object` rather than `Out-File` if you want to read partial output mid-run.
3. Look for `*_start` log lines without a matching `*_complete` — that's where real I/O is blocking.
4. Suspect any module that calls `aembedding`, `acompletion`, or any `litellm.*` function without a test stub.
**Fix pattern:** Autouse fixture (per file or in `conftest.py`) that monkeypatches the I/O function AT THE CONSUMER BINDING. Module-level `from X import Y` captures the binding once → patching `X.Y` is useless. You must patch `consumer_module.Y` too. For embeddings: patch BOTH `app.llm.embeddings.embed` AND `app.stopping.signals.saturation.embed`.
**Reference fixture:** see `_stub_embeddings` in `backend/tests/test_agent_orchestrator.py`.

---

## L-029: Reuse meta-judge orchestration via a hook helper, not by duplicating logic (2026-05-28, IP-26 slice 3b)
**Context:** Slice 2 placed meta-judge logic inline inside `AgentOrchestrator._maybe_run_meta_judge`. Slice 3b needed the same logic from DEEP lane's `after_cove` lifecycle point — a tempting copy-paste would have diverged immediately (different judge-signal source, different stop-reason mapping, different return semantics).
**Lesson:** Extract a single async helper that takes a `hook: MetaJudgeHook` literal and returns a `MetaJudgeOutcome` literal (`stop_best_effort` / `confirm` / `continue` / `skipped`). Callers do the lane-specific state mutation (set `state.final_answer`, return the right `StopReason`). The helper owns: skip gating, VoC call, AC pass (when `continue` + `expected_delta_s` threshold), sub-claim minting, and event emission tagged with `hook`.
**Why it matters:**
1. Single-place change for AC threshold / event payload shape.
2. Every hook emits `MetaStopVerdictEvent` with `hook="..."` so FE can attribute the verdict source.
3. New hooks (e.g. `after_react_observation`) wire in by adding one literal value + one call site — no orchestration logic duplicated.
**Anti-pattern:** Calling `evaluate_value_of_continuation` and `generate_adversarial_objections` directly from a new lane — you'll re-implement skip gating and sub-claim minting and they'll drift.
**Critical test-side corollary:** module-level `from app.llm.meta_judge import evaluate_value_of_continuation` in `meta_judge_hook.py` means tests MUST monkeypatch `app.agent.meta_judge_hook.evaluate_value_of_continuation`, NEVER `app.llm.meta_judge.evaluate_value_of_continuation`. Patching the source module has no effect once the consumer's binding is captured. Same rule as L-030.

---

## L-028: Coder MUST run pyright + full pytest before reporting done (2026-05-28, IP-25 Phase F)
**Context:** Phase F Coder reported "implementation complete" with only ruff + individual cove tests run. Orchestrator validation revealed 18 pyright errors and 10 test failures (cascading: wrong registry API, `SynthesizedAnswer` passed where `str` expected, missing monkeypatches, ≥2 hypotheses constraint, StrEnum case sensitivity).
**Lesson:** Every Coder handoff MUST include explicit pyright + full pytest output as evidence. Skipping these costs an extra Orchestrator validation cycle and may hide cascading bugs.
**Enforcement:** Orchestrator MUST refuse to launch Reviewer until Coder provides clean pyright + green full pytest.
**Specific patterns to verify on every CoVe-like integration:**
1. `SourceRegistry` API is `.types() -> list[SourceType]` and `.get(type) -> Source`. NEVER `.all_sources()`.
2. DEEP lane `_synthesize_*` helpers return `SynthesizedAnswer`. Use `.prose` to feed string-typed downstream consumers (CoVe, mini-judge).
3. `LLMRole` is StrEnum → `str(LLMRole.JUDGE) == "judge"` (lowercase). Assertions must use case-insensitive comparison.
4. `generate_hypotheses` requires `len(items) ≥ 2`. Test fixtures returning 1 item raise `ValueError`.
5. When a function imports `get_registry` at runtime inside a block, tests monkeypatch the module that imports it (`app.agent.tasks.cove.get_registry`) — keep the import seam single and consistent so all monkeypatches converge.

---

## L-027 — SourceResult schema has `content`/`snippet`, never `text` or `authority_tier`
**Date:** 2026-05-28 (origin: IP-25 Phase E iter 1 review — Coder accessed `result.text` which doesn't exist on SourceResult. Fixed in iter 2 with `result.content or result.snippet` pattern).

**Rule:** The `SourceResult` Pydantic model ([seams/source.py](backend/app/seams/source.py#L23-L31)) has exactly these fields:
```python
url: str
title: str
snippet: str           # ← Short excerpt
content: str | None    # ← Full text (if fetched)
relevance_score: float | None
published_date: str | None
```

**Common bugs:**
- Accessing `result.text` → AttributeError (no such field)
- Accessing `result.authority_tier` → AttributeError (authority is computed post-search, not part of SourceResult)
- Passing `source_published_date` or `authority_tier` to `EvidenceAddedEvent` from a `SourceResult` object

**Correct patterns:**
```python
# For short text: use snippet
text = result.snippet

# For long text: prefer content, fallback to snippet
text = result.content or result.snippet

# For EvidenceAddedEvent: only pass SourceResult fields that exist
await emit(EvidenceAddedEvent(
    source_url=result.url,
    source_title=result.title,
    extracted_text=(result.content or result.snippet)[:500],
    # ❌ DO NOT: source_published_date=result.published_date (wrong type)
    # ❌ DO NOT: authority_tier=result.authority_tier (doesn't exist)
))
```

**Why this trips people up:**
- In natural language, "text" is the obvious field name for textual content.
- The field split (`snippet` vs `content`) reflects Source plugin implementation: `search()` returns short snippets, `fetch_full()` populates `content`.
- LLM plans may hallucinate extra fields like `authority_tier` that sound plausible but don't exist in SourceResult (they're computed separately in the confidence layer).

**Symptoms:**
- AttributeError: 'SourceResult' object has no attribute 'text'
- AttributeError: 'SourceResult' object has no attribute 'authority_tier'
- Pydantic ValidationError when emitting EvidenceAddedEvent with wrong field types

**Mitigation:**
- Always consult `backend/app/seams/source.py` SourceResult schema before accessing fields
- In reviews, verify any SourceResult field access against the schema
- When mocking SourceResult in tests, use real field names to catch bugs early

**Reference:**
- IP-25 Phase E iter 1 review: [REVIEW-IP-25-Phase-E.md](docs/implementation-phase/reviews/REVIEW-IP-25-Phase-E.md#C1) lines 61-92
- Fixed in iter 2: [loop.py#L318](backend/app/agent/react/loop.py#L318), [#L379](backend/app/agent/react/loop.py#L379)

---

## L-026 — Always verify event kwargs match Pydantic schema before emitting
**Date:** 2026-05-28 (origin: IP-25 Phase E iter 1 fixes — Coder emitted `EvidenceAddedEvent` with bogus `source_published_date` and `authority_tier` fields that don't exist on SourceResult. Tests passed with mocks but would fail in production).

**Rule:** Before calling `emit(SomeEvent(...))`, cross-reference the event's Pydantic schema definition in `backend/app/domain/events.py` to verify:
1. All required fields are provided
2. All provided fields exist in the schema
3. Field types match (e.g., `datetime | None`, not `str | None`)
4. Source of data has the field (e.g., don't pass `SourceResult.authority_tier` — it doesn't exist)

**Common bugs:**
- Passing extra fields that sound plausible but aren't in the schema (e.g., `source_published_date` when the schema expects no such kwarg)
- Passing fields from an upstream object that doesn't have them (e.g., passing `result.authority_tier` when SourceResult lacks that field)
- Tests pass because mocks accept arbitrary kwargs, but production crashes on real objects

**Correct pattern:**
```python
# 1. Read the event schema first
class EvidenceAddedEvent(BaseEvent):
    source_type: SourceType
    source_url: str
    source_title: str
    extracted_text: str
    polarity: EvidencePolarity
    target_claim_id: str
    confidence: float
    source_published_date: datetime | None = None  # ← Optional
    authority_tier: AuthorityTier | None = None    # ← Optional

# 2. Emit with only valid fields from your source object
await emit(
    EvidenceAddedEvent(
        source_type=source_type,
        source_url=result.url,          # ← SourceResult has .url
        source_title=result.title,      # ← SourceResult has .title
        extracted_text=(result.content or result.snippet)[:500],  # ← Valid fields
        polarity=EvidencePolarity.SUPPORTS,
        target_claim_id="react_search",
        confidence=0.7,
        # ❌ DO NOT add source_published_date or authority_tier here
        # unless you're computing them separately (not available on SourceResult)
    )
)
```

**Why this trips people up:**
- Pydantic's `extra="allow"` on BaseEvent means extra kwargs are silently accepted at **event creation** but cause validation errors when **persisting to DB** or **regenerating frontend types**.
- Mocks in tests don't enforce schema, so tests pass even with wrong kwargs.
- LLM code generation may infer plausible-sounding fields that don't exist.

**Symptoms:**
- Tests pass locally but fail in integration with real objects
- ValidationError when persisting events to database
- Frontend types mismatch after regenerating from backend schema

**Mitigation:**
- Add a review step: "Verify event kwargs match schema definition"
- In tests, prefer using real Pydantic models over mocks when possible
- In reviews, cross-check every `emit(Event(...))` call against `events.py` schema

**Reference:**
- IP-25 Phase E iter 1 additional fixes: Corrected `EvidenceAddedEvent` calls in [loop.py#L331-339](backend/app/agent/react/loop.py#L331) and [#L396-404](backend/app/agent/react/loop.py#L396)
- See L-027 for SourceResult field reference

---

## L-025 — When a plan specifies enum-based conditionals, verify the values exist in the correct enum (QuestionType vs AnswerKind)
**Date:** 2026-05-28 (origin: IP-25 Phase D iter 1 review — plan §6.2 T-25-D-04 said `state.question_type in {CAUSAL, SCENARIO, PREDICTIVE_FUTURE, BEST_EFFORT}` but SCENARIO and BEST_EFFORT are `AnswerKind` values, not `QuestionType` values. Coder correctly split the condition into `question_type in {CAUSAL, PREDICTIVE_FUTURE} OR selected_answer_kind in {SCENARIO, BEST_EFFORT}` by consulting `domain/enums.py`).

**Rule:** Before implementing an enum-based conditional from a plan, **verify every enum value exists in the claimed enum**. The domain model may have multiple orthogonal enums (QuestionType, AnswerKind, StopReason, Lane) and specs can conflate them.

**Pattern**
- Read `backend/app/domain/enums.py` to see available values per enum.
- If the plan says `question_type in {A, B, C}`, grep enums.py for `class QuestionType` and verify A, B, C are listed.
- If values span multiple enums, split the condition across axes (e.g., `question_type in {X} OR answer_kind in {Y}`).

**Why this trips people up**
- "Causal" and "scenario" sound semantically related, so it's natural to assume they're in the same enum.
- A plan author may sketch pseudo-code without checking the actual types.
- The spec may evolve: SCENARIO was initially a question type in early design, then migrated to AnswerKind during the "always answer" refactor.

**Symptoms to watch for**
- `AttributeError: type object 'QuestionType' has no attribute 'SCENARIO'` at runtime.
- Pyright errors about unknown enum members at import time (if you're lucky).
- Trigger condition that never fires because the values don't exist where you're checking.

**Mitigation**
- Always consult `backend/app/domain/enums.py` before implementing enum conditionals.
- When a spec mentions multiple values, validate they're all in the same enum OR split the logic.
- In reviews, flag any enum-based condition and verify against enums.py (see REVIEW-IP-25-Phase-D.md §"Correct deviation from plan").

**Reference commits**
- IP-25 Phase D iter 1: Coder correctly fixed plan bug by splitting SCENARIO/BEST_EFFORT into `selected_answer_kind` check.
- Review report: `docs/implementation-phase/reviews/REVIEW-IP-25-Phase-D.md` Architecture Compliance §"Positive highlight".

---

## L-024 — pyright type narrowing requires the narrowed type to be imported
**Date:** 2026-05-28 (origin: IP-25 Phase C iter 2 → 3 — 27 pyright errors in `fast.py` all traced to missing `from app.seams.source import SourceResult`. After `isinstance(results, BaseException)` check at line 101, pyright should narrow `results: list[list[SourceResult]]` but without the import, the name `SourceResult` is unknown, so all downstream `result.url`, `result.title`, `result.snippet` accesses become `reportUnknownMemberType` errors).

**Rule:** When you write `isinstance(x, SomeType)` or match-case type narrowing, pyright needs `SomeType` to be in scope (imported or defined locally). If the type comes from a protocol method return annotation (e.g., `Source.search() -> list[SourceResult]`), **you still need to import the type explicitly** for narrowing to work, even though the runtime doesn't require it.

**Pattern**
- Protocol-based APIs: If a protocol method like `Source.search()` returns `list[SourceResult]`, the *caller* must import `SourceResult` for type narrowing to work, even though the protocol itself imports it.
- Fix: Add `from app.seams.source import SourceResult` alongside other imports.
- Symptom: Cascade of `reportUnknownMemberType` / `reportUnknownArgumentType` errors on a variable you *know* is correctly typed at runtime.

**Why this trips people up**
- The code runs fine (Python's duck typing doesn't care about the import).
- The protocol definition has the type, so it *feels* like it should be available transitively.
- Pyright's type narrowing is a compile-time analysis feature — it requires the name to be in the current scope.

**Symptoms to watch for**
- Many `reportUnknownMemberType` errors clustered around a variable whose type you control.
- The variable's type is correct per the function signature but pyright doesn't recognize member access.
- A single missing import causes 10+ downstream errors.

**Mitigation**
- Run pyright incrementally during development (`python -m pyright <file>`), not just at pre-commit.
- When you see cascading unknown-member errors, check if the type name is imported.
- For protocol-based seams, import both the protocol (`Source`) *and* the data types it returns (`SourceResult`).

**Reference commits**
- IP-25 Phase C Fix PC5 (iter 2→3): Added `from app.seams.source import SourceResult` → 27 errors → 0.
- Review report: `docs/implementation-phase/reviews/REVIEW-IP-25-Phase-C.md` iter 2 + 3.

---

## L-023 — A bounded additive bump cannot differentiate samples whose base score already sits at the clamp ceiling
**Date:** 2026-05-28 (origin: C6 citation-weighted ranking — first run of the new tests for `semantic_scholar` and `openalex` failed with `assert 1.0 > 1.0` because both the cited and uncited fixtures landed at rank 0, where base `relevance_score = max(0.1, 1.0 - 0*0.05) = 1.0`. The +0.30 citation bump was clipped by `min(1.0, base + bump)` and the cited result tied the uncited one).

**Rule:** When testing (or relying on) a score-adjustment helper of the form `final = clamp(base + delta(x))`, the assertion `final(x_high) > final(x_low)` only holds where `base + delta(x_high) < ceiling`. If you control the fixture, put the sample at a rank/base that leaves headroom for `delta_max`; never test the differentiation property at a position where the clamp is guaranteed to bite.

**Pattern**
- Source plugins assign `base = max(0.1, 1.0 - rank * step)`. For `step = 0.05` and `delta_max = 0.30`, headroom appears at `rank >= 6`. The C6 tests pad with 5 placeholders so the target sits at rank 5 (base 0.75): cited → `min(1.0, 0.75 + 0.30) = 1.0`, uncited → `0.75 + 0 = 0.75`. The differentiation is now observable.
- Mirror the math in the test docstring so a future reader sees *why* rank 5 was chosen, not just that it works.
- Keep the bump itself uncapped-by-clamp in unit-tests of the helper (`_citation_bump` is tested in isolation: log-scaled, monotonic, capped at 0.30); only test the *integration* property at a non-saturated base.

**Why this trips people up**
- The production effect is real: citation bumps DO break ties at lower ranks where search-engine relevance is uncertain. They DON'T (and shouldn't) override a top-ranked Tavily/Wikipedia hit. The test must reflect the production scenario where the bump matters, not the impossible-to-differentiate edge case.
- It's tempting to "fix" the failure by raising `delta_max` or removing the clamp. Both are wrong: the clamp is the contract (`relevance_score ∈ [0, 1]`), and `delta_max = 0.30` is what keeps search-engine ranking dominant.

**Symptoms to watch for**
- Tests of the shape `assert score_high > score_low` failing with `1.0 > 1.0` (or `0.0 == 0.0` at the floor).
- A flaky differentiation test that passes only when the fixture happens to land at a non-zero rank.

**Mitigation**
- For any new ranking/scoring helper added to a Source plugin: write three tests — (a) helper-in-isolation (math), (b) helper-in-integration at a non-saturated rank, (c) idempotence at the ceiling/floor (no NaN, no exception).
- When padding fixtures to reach a target rank, comment the base-score arithmetic next to the pad list.

**Reference commits**
- `87252c4` (this session, C6) — Semantic Scholar + OpenAlex citation-weighted ranking. Tests `test_search_relevance_score_lifts_well_cited_paper` / `_work` pad with 5 placeholders so the target sits at rank 5.
- Cross-reference: D-AGENT-ROBUSTNESS in `decisions-history.md`.

---

## L-022 — `llm.call` prepends the system prompt; tests must inspect `messages[-1]`, not `messages[0]`
**Date:** 2026-05-28 (origin: C2 unified-judge-threshold test — the assertion `"0.73" in messages[0]["content"]` failed because `app/llm/client.py::call` injects `{"role": "system", "content": ROLE_PROMPTS[role]}` as the first message before forwarding to `litellm.acompletion`. The mocked `client.chat.completions.create` therefore receives `messages=[system, user]` and the threshold string lives on the user message at index `-1`).

**Rule:** Any unit test that mocks the LLM transport and inspects the prompt payload MUST address messages by role or by `[-1]` (the most recent user turn), NEVER by `[0]`. This holds for every agent task (`classify`, `plan`, `analyze`, `draft`, `judge`, `decompose`) because all of them route through `llm.call(role, user_messages, …)`.

**Pattern**
```python
# CORRECT — assert against the user turn
messages = mock_create.call_args.kwargs["messages"]
assert messages[-1]["role"] == "user"
assert "0.73" in messages[-1]["content"]

# BROKEN — messages[0] is always the system prompt
assert "0.73" in mock_create.call_args.kwargs["messages"][0]["content"]
```

**Why this trips people up**
- The `llm.call` signature accepts `user_messages: list[ChatMessage]` so the natural mental model is "index 0 is what I passed in". The system-prompt injection is a layer below that the agent code never sees.
- A passing test that asserts on `[0]` is a sign the role prompt itself contains the expected substring — which means the test isn't actually verifying the agent task's own behaviour.

**Symptoms to watch for**
- `AssertionError: assert '<short string>' in '<long system prompt>'`.
- Tests that pass with the assertion text matching well-known role-prompt vocabulary ("You are a judge", "approve", "reject", …).

**Mitigation**
- New helper recommended for `tests/conftest.py` (not yet added): `def user_message(mock_create) -> dict: return mock_create.call_args.kwargs["messages"][-1]`.
- When auditing existing tests, grep `messages\[0\]\["content"\]` under `backend/tests/` — anything inspecting prompt body should switch to `[-1]`.

**Reference commits**
- `4c918a5` (this session, C2) — `refactor(judge): unify threshold`. Test `test_judge_prompt_includes_threshold` was authored against `[0]`, then corrected to `[-1]` in the same commit after the first pytest run failed.

---

## L-021 — UI microcopy stays English; only the LLM-generated answer follows the user's language
**Date:** 2026-05-28 (origin: a prior session shipped Spanish storytelling labels in `RunFeed` / `Trace` per a user request, then this session the user reversed the directive — "todo debe ser en inglés, solo las respuestas podrían ser en otro idioma si es que el usuario pregunta en un idioma diferente").

**Rule:** Every hardcoded UI string in the frontend (labels, buttons, aria-labels, narratives, idle reassurance, microcopy constants, fallback strings) MUST be English. The only multilingual surface is the final LLM-generated answer, which the system prompt (`backend/app/llm/prompts.py`) tells the model to render in the user's language. Do NOT translate UI strings to match the user's chat language, even if the user previously asked for it — the project language policy overrides single-session requests.

**Why this trips people up**
- A user writing Spanish naturally feels Spanish UI is "nicer"; agents over-fit to the conversation language.
- Spanish UI strings then leak into Vitest assertions, doubling the migration cost when the policy is re-enforced (this session: 10 test files + 9 source files churned).

**Pattern**
- Source of truth for copy: `frontend/src/lib/microcopy.ts`, `frontend/src/lib/eventLabels.ts`, `frontend/src/lib/idleMessages.ts`. All English.
- Component fallbacks (e.g. `"Working on it"`, `"Thinking…"`, `"no events yet"`) → English.
- LLM answer language → governed by prompt, never by UI strings.
- Assistant chat replies to the user MAY follow user language (this is meta-conversation, not product UI).

**Symptoms to watch for**
- A grep `[áéíóúñ]` over `frontend/src/**/*.{ts,tsx}` returning matches outside test fixtures.
- Vitest assertions like `/ocultar/i`, `expect(...).toHaveTextContent("evento")`, `screen.getByText("Confirmado")`.
- New PRs adding Spanish strings to atoms / molecules.

**Mitigation**
- Before shipping, run: `Select-String -Path frontend/src/**/*.{ts,tsx} -Pattern "ocultar|mostrar|fuente|resultado|veredicto|confianza|umbral|razonamiento|pensando|trabajando"`.
- Treat user requests like "ponlo en español" as scoped to the chat reply, NOT to product strings; confirm before changing UI copy.

**Reference commits**
- `5e070bc` (this session) — translates feed/trace microcopy back to English after `8040be8` + `144e500` accidentally landed Spanish copy.
- Memory: `/memories/language-policy.md` updated to explicitly list "UI microcopy" under hardcoded strings.

---

## L-020 — SVG diagrams that rely on a wide viewBox MUST be hidden below `sm` (640 px)
**Date:** 2026-05-29 (origin: HowWeWorkPage `PipelineDiagram` — a 1200×520 viewBox SVG with 9 nodes was rendered on iPhone-class viewports and the user reported the boxes were unreadable / invisible).

**Rule:** Any decorative or explanatory SVG whose internal layout assumes ≥ ~800 px of horizontal room MUST be wrapped in a container that carries `hidden sm:block` (or equivalent `md:` if even tablet is too tight). The page keeps the surrounding title + description so the section still makes sense; only the diagram is dropped on mobile.

**Why not just shrink it?** Scaling a 1200-px-wide vector down to 380 px collapses stroke widths, gradient bboxes (see L-019) and label spacing past legibility. Hiding is honest; squashing pretends the diagram still communicates.

**Pattern**
```tsx
<motion.div className="hidden sm:block ...">
  <DiagramSVG />
</motion.div>
```

**Symptoms to watch for**
- Reviewer screenshot from a mobile device shows the diagram container as a black/empty box.
- Nodes appear but text labels overflow / overlap.
- A `viewBox` ratio wider than ~2.3 : 1 on a section that also has a descriptive paragraph.

**Mitigation**
- Default for any new pipeline / lane / timeline SVG: `hidden sm:block`.
- If the diagram is load-bearing (the section makes no sense without it), build a mobile-first vertical variant instead of cramming the desktop one.

---

## L-019 — Flat horizontal SVG paths cannot use `linearGradient` with default `objectBoundingBox` units
**Date:** 2026-05-29 (origin: HowWeWorkPage `PipelineDiagram` — three horizontal connectors at y = 260 rendered as invisible strokes because their bounding box has zero height, collapsing the gradient).

**Rule:** `<linearGradient>` defaults to `gradientUnits="objectBoundingBox"`. When a stroked path is perfectly flat on one axis, that axis of the bbox has zero size and the gradient degenerates. For any flat segment, either:
1. Switch to a solid `stroke="rgba(...)"` token (the fix applied — see commit `974c7c4`), or
2. Set `gradientUnits="userSpaceOnUse"` on the `<linearGradient>` and provide absolute `x1/y1/x2/y2`.

**Symptoms to watch for**
- Path is present in the DOM, hit-testable, but visually missing.
- The same gradient renders fine on curved siblings (which have non-zero bbox on both axes).
- DevTools shows the path with `stroke="url(#grad-...)"` but no color.

**Mitigation**
- For connector lines in pipeline diagrams, prefer solid token strokes (`rgba(99,102,241,0.7)` for indigo, `rgba(251,191,36,0.85)` for amber). Reserve gradients for arcs/curves where the bbox is naturally 2D.

---

## L-018 — Slate Aurora is MANDATORY across the whole app, not a landing-page treatment
**Date:** 2026-05-29 (origin: the HowWeWorkPage `/` landing established the canonical visual language — animated background orbs, glass surfaces, canonical button recipes, gradient-text headline, `fadeUp + stagger` scroll-reveal — and the user explicitly required these patterns to apply everywhere).

**Rule:** Every page, modal, organism and atom MUST implement the Slate Aurora patterns defined in `docs/understanding-phase/ui-design.md` §0 (mandatory preamble) and §11 (Pattern lock-in table, 12 irreplaceable patterns). Reviewers MUST reject PRs that:
- Use solid `bg-black` / `bg-gray-*` / `bg-slate-*` Tailwind classes instead of token-bound surfaces.
- Reinvent button styles inline instead of going through the `Button` atom (variants `primary` / `secondary` / `ghost` / `danger`).
- Skip `BackgroundOrbs` on a full-viewport route (`AppShell` paints it for authenticated pages; standalone pages render it directly).
- Use gradient text outside the two whitelisted locations (hero `<h1>` highlight and confirmed-answer confidence value).
- Skip the `fadeUp + stagger` preset for sections below the fold.
- Hardcode hex / rgb values; tokens are the only allowed source.

**Where to find the canonical recipes**
- Background orbs: `ui-design.md` §2.9 + `frontend/src/pages/HowWeWorkPage.tsx` lines 84–117 (reference impl).
- Button CTAs: `ui-design.md` §6.1.1 (verbatim Tailwind classes).
- Scroll-reveal: `ui-design.md` §5.3 + `frontend/src/lib/motion.ts` (when extracted).
- Gradient text: `ui-design.md` §6.8.
- Pill chip + top-bar glass: `ui-design.md` §6.9 / §6.10.

**Override clause:** any prior text in this memory bank, in component docstrings, or in `ui-prototype.md` that contradicts §11 is **superseded by §11**. The lock-in table is the contract.

---

## L-017 — Subagent edits over large blocks can land in the wrong scope; re-read after every Coder edit
**Date:** 2026-05-27 (origin: IP-22 Phase 4/5 — Coder injected the `PriorRunHintReplayed` rendering branch inside `formatRelativeTime()` instead of `EventNode`, producing dead JSX and breaking the entire `EventNode.test.tsx` transform).

**Rule:** After invoking the Coder subagent on any file with > ~50 LOC affected, the Orchestrator (or the developer reviewing the change) MUST `read_file` the modified region and verify scope/syntax before running tests. Subagent self-reports are intent, not verification.

**Symptoms to watch for**
- `Transform failed` / `Expected "}" but found ";"` in vitest — usually a stray `})` or missing closing tag.
- 0 tests collected in a previously working file.
- Logic that "should run" silently never executes (cold dead branches).

**Mitigation**
- Prefer many small `replace_string_in_file` edits over one big block rewrite.
- After Coder finishes a phase, run the phase's affected test files in isolation BEFORE the full suite — failures localize faster.

## L-016 — Trivial-path tests need to budget for skip-critique semantics
**Date:** 2026-05-27 (origin: IP-22 — 33 orchestrator tests failed after introducing `critique_passes_target=0` for TRIVIAL/FACTUAL paths because pre-BRD-22 tests assumed PLANNING→CRITIQUING→REVISING always ran).

**Rule:** When a state machine adds a skip-edge (e.g. PLANNING→SEARCHING when `target==0`), audit and update existing tests that hard-code intermediate states.

**Specific gotchas**
- Tests using a default short question (e.g. "What is the capital of France?") now hit the trivial path; lengthen the question (≥ 9 words) to keep the legacy STANDARD/DEEP flow.
- LLM stub queues sized for "always critique" exhaust early in the new flow — add a couple of extra synth/judge pairs as safety margin.
- The state machine's allowed-transitions table is now part of the test contract; add the new edge BEFORE the implementation lands or every related test breaks at once.

---

## Pre-existing lessons

- **L-015:** Every New RunState Field Needs an Explicit Folding Strategy (2026-05-27)
- **L-014:** A Working FSM + a Working SSE Stream Do Not Imply a Working Product — the Runtime Bridge is its Own BRD (2026-05-26)
- **L-013:** `...init` Spread in `fetch()` Options Must Come Before `headers`/`body` (2026-05-26)

---

## L-015: Every New RunState Field Needs an Explicit Folding Strategy

**Date:** 2026-05-27
**Agent:** Auditor (AUDIT-IP-22 iter 1)
**Category:** Backend / Agent FSM / RF-03

### Situation
IP-22 added two new fields to `RunState`: `critique_passes_target: int = 1` and `critique_passes_completed: int = 0`. The plan stated these would be used by the orchestrator during the `CRITIQUING` state to enforce per-complexity critique budgets, but did NOT specify how they would be reconstructed during event replay (resume/fork).

The Auditor identified this as a **major blind-path finding**: when replaying a run that stopped mid-critiquing, `_fold_events` could not reconstruct `critique_passes_completed` from the event log alone because the counter was incremented in-memory but never emitted in an event. The replayed state would default to `0`, causing the orchestrator to potentially re-run critiques that had already completed.

### Root Cause
The plan violated RF-03's **replay determinism** contract. Every state transition that affects orchestrator control flow must either:
1. Be stored in an event (so `_fold_events` can fold it), OR
2. Be deterministically recomputable from existing events, OR
3. Be stored in a field on an existing event (e.g. new optional field on `PlanCreatedEvent`).

The plan chose (3) for `complexity_hint` and `expected_experts` (correctly), but did NOT choose any of the three for `critique_passes_target` or `critique_passes_completed`.

### Fix
The Auditor recommended: **Recompute during fold.** Recompute `critique_passes_target` from the budget table using `(state.question_type, state.complexity_hint)` (deterministic). Compute `critique_passes_completed` as `len([e for e in events if e.type == EventType.PLAN_CRITIQUED])`.

### Prevention Rule
When any task in an Implementation Plan adds a field to `RunState`:
- [ ] The task MUST include a sentence stating: *"Update `_fold_events` to fold this field by [recomputing from X / reading from event Y / defaulting to Z when missing]."*
- [ ] If the field affects FSM control flow (branches, loop counters, budget gates), the folding strategy MUST be deterministic — no silent defaults that silently change behavior on replay.
- [ ] The Auditor MUST flag any new `RunState` field without an explicit folding strategy as a **major blind-path finding**.

### Pattern in the wild
This is the THIRD occurrence of this pattern in the project:
1. **IP-07** (Agent FSM) — `RunState.question_type`, `RunState.sub_claims`, `RunState.evidence` all had explicit folding in the original `_fold_events`.
2. **IP-15** (Fork & Resume) — `RunState.parent_run_id`, `RunState.forked_from_event_id` added with explicit folding strategy.
3. **IP-22** (this finding) — `RunState.critique_passes_target`, `RunState.critique_passes_completed` added WITHOUT folding strategy → audit finding.

Each time the pattern appears, it blocks approval at F2. The rule above should make this the LAST time.

---

## L-013: `...init` Spread in `fetch()` Options Must Come Before `headers`/`body`
- **L-012:** Float-Boundary Tests for Strict-`>` Thresholds Must Use Exact IEEE-754 Values (2026-05-26)
- **L-011:** Drive Interval-Backed Components from a Prop in Tests, not from Fake Timers (2026-05-26)
- **L-010:** Cancellation Tests in Single-Task Async FSMs Need a Yielding Emit Hook (2026-05-27)
- **L-009:** Vitest Fake Timers — `advanceTimersByTime` Already Moves `Date.now()`; Do Not Call `setSystemTime` Again (2026-05-27)
- **L-008:** Always Prefix Backend API Calls with `API_URL` — MANDATORY RULE (2026-05-26)
- **L-007:** Upgrading a Header-Only Auth Fixture Requires Touching All Downstream Route Tests (2026-05-26)
- **L-006:** `exactOptionalPropertyTypes` Requires `prop?: T | undefined` on Pass-Through Props (2026-05-26)
- **L-005:** SQLite Fallback for PG-Typed ORM Tests via `compiles`-hooks (2026-05-26)
- **L-004:** Disable the `pytest-postgresql` Plugin When Running DB-Free Suites Locally (2026-05-26)
- **L-003:** Static-Only Tests for DB Migrations are Acceptable for Iteration 1 (2026-05-26)
- **L-002:** Unit Tests are Mandatory per F3.S3 (2026-05-26)
- **L-001:** BRD Template for Spec-Driven Development (2026-05-26)

---

## L-013: `...init` Spread in `fetch()` Options Must Come Before `headers`/`body`

**Date:** 2026-05-26
**Agent:** All agents
**Category:** Frontend / HTTP / Bug

### Situation
`POST /api/runs` returned FastAPI error 422: `"Input should be a valid dictionary or object to extract fields from"`. The request body was arriving as a raw JSON string instead of a parsed object.

### Root Cause
In `lib/api.ts`, the spread `...init` was placed **after** `headers` and `body` in the `fetch()` options object:

```typescript
// ❌ BROKEN — ...init overrides headers (and body) if init contains those keys
fetch(url, {
  method: "POST",
  headers: { "Content-Type": "application/json", ...init?.headers },
  body: JSON.stringify(body),
  ...init,   // ← if init has {headers: {...}}, it wipes Content-Type!
});
```

`createRun` passed `init = { headers: { "X-Username": ..., "X-Token": ... } }`. The final spread replaced the entire `headers` object, silently dropping `Content-Type: application/json`. FastAPI received the body as `text/plain`, could not deserialize it, and rejected it as a string literal.

### Fix
Move `...init` **before** the explicit keys so the explicit values always win:

```typescript
// ✅ CORRECT — explicit headers and body always take precedence
fetch(url, {
  method: "POST",
  ...init,
  headers: { "Content-Type": "application/json", ...init?.headers },
  body: JSON.stringify(body),
});
```

This was applied to all four methods in `api.ts`: `get`, `post`, `put`, `delete`.

### Prevention
- Rule: in any `fetch(url, { ...init, headers: {...}, body: ... })` pattern, `...init` must be the first key after `method`.
- Test: assert `Content-Type: application/json` is present in the `fetch` call in any hook test that passes auth headers.
- Code review: flag any `...init` or `...options` spread placed after `headers` or `body` in a `fetch()` call.

---

## L-012: Float-Boundary Tests for Strict-`>` Thresholds Must Use Exact IEEE-754 Values

**Date:** 2026-05-26
**Agent:** Coder (BRD-08 / IP-08 — confidence calculation)
**Category:** Backend / Testing / Floating-Point

### Problem
When testing `detect_mismatch(structural, judge, threshold)` at the boundary where `divergence == threshold` must *not* trigger (strict `>`), using human-friendly decimals fails:

```python
# FAILS: 0.8 - 0.6 == 0.20000000000000007 in IEEE-754
result = detect_mismatch(structural=0.8, judge=0.6)  # threshold=0.2 default
assert result.has_mismatch is False  # AssertionError
```

`0.2`, `0.6`, `0.8` are all non-terminating in binary; the subtraction overshoots by ~1e-16 and the strict `>` fires.

### Fix
Use exact IEEE-754 values (sums/differences of powers of 2 — `0.5`, `0.25`, `0.125`, `0.75`, …) so the assertion is deterministic:

```python
# Exact: 0.5 - 0.25 == 0.25 in IEEE-754
result = detect_mismatch(structural=0.5, judge=0.25, threshold=0.25)
assert result.has_mismatch is False  # passes
```

### Rule
- Strict-`>` boundary assertions: pick operands whose binary representation is exact.
- Non-boundary float assertions: always wrap with `pytest.approx`.
- Document the choice with an inline comment so the test doesn't look like an arbitrary value.

---

## L-011: Drive Interval-Backed Components from a Prop in Tests, not from Fake Timers

**Date:** 2026-05-26
**Agent:** Coder (BRD-13 iter 2 — CR-13-002 fixes)
**Category:** Frontend / Testing / Vitest

### Situation
`ElapsedClock` has an internal `setInterval` that reads `Date.now()` each second. The iter-2 spec validated the tick by combining `vi.setSystemTime(t0)` + `vi.advanceTimersByTime(3_000)`. In isolation the test asserted `"3s"`; in the full suite it received `"6s"` — exactly the L-009 double-advance pitfall.

### Lesson
When a component already exposes an injectable clock prop (`now?: Date`), tests should drive elapsed time through that prop with `render` + `rerender`, and use fake timers only for the orthogonal "the interval is wired" assertion (and even then, prefer `vi.advanceTimersByTime` alone — never with `vi.setSystemTime`). Asserting *that the text changed* is safer than asserting a specific tick value when fake-timer state may be shared across the suite.

### Pattern
```tsx
// Stable: prop-driven elapsed
const { rerender } = render(<ElapsedClock startedAt={t0} now={new Date(t0)} />);
expect(screen.getByTestId("elapsed-clock")).toHaveTextContent("0s");
rerender(<ElapsedClock startedAt={t0} now={new Date(t0Plus3s)} />);
expect(screen.getByTestId("elapsed-clock")).toHaveTextContent("3s");

// Interval-existence only — no setSystemTime
vi.useFakeTimers();
render(<ElapsedClock startedAt={isoNowMinus1s} />);
const before = screen.getByTestId("elapsed-clock").textContent;
act(() => { vi.advanceTimersByTime(2_000); });
expect(screen.getByTestId("elapsed-clock").textContent).not.toBe(before);
vi.useRealTimers();
```

### Why it Matters
Reinforces L-009 with a concrete pattern: any component that already accepts a "now" prop should be tested through that seam in the assertion path, leaving the timer machinery for the existence check only.

## L-010: Cancellation Tests in Single-Task Async FSMs Need a Yielding Emit Hook

**Date:** 2026-05-27
**Agent:** Coder (BRD-07 — `AgentOrchestrator`)
**Category:** Backend / Testing / Asyncio

### Situation
`AgentOrchestrator.cancel()` sets `self._cancelled = True`, checked at the top of each `run()` loop iteration. The intuitive test pattern — wrap `orch.run()` in `asyncio.create_task`, then call `orch.cancel()` from the outer task — does not work when every LLM call and source call is mocked with synchronous `AsyncMock`s that never `await`-yield. The whole `run()` coroutine executes in a single scheduling slot before the outer task can run, so the cancel flag is set after `Stopped` has already been emitted with `judge_confirmed`.

### Lesson
For unit tests of a single-task async FSM with mocked I/O, inject cancellation via the **event callback** instead of an external task. The callback is `await`-ed inside the loop body, so an `await asyncio.sleep(0)` there gives the test a deterministic yielding point:

```python
async def cancelling_emit(event: BaseEvent) -> None:
    captured.append(event)
    if isinstance(event, PlanCritiquedEvent):
        await asyncio.sleep(0)
        orch.cancel()

stop_reason = await orch.run()  # no outer task, no race
assert stop_reason is StopReason.USER_CANCELLED
```

This keeps the orchestrator's public API unchanged (`cancel()` still works the way the worker will use it in BRD-10) while making the cancellation path unit-testable without a real `asyncio.Task` race.

### Prevention
- For any future FSM with `_cancelled`-style cooperative cancellation, write the cancel test against the emit hook, not against an outer task.
- Document in the orchestrator docstring that the worker (BRD-10) is responsible for running the orchestrator in its own task — the cancel flag is correct, but the timing depends on a real event loop yielding on real I/O.

---

## L-009: Vitest Fake Timers — `advanceTimersByTime` Already Moves `Date.now()`; Do Not Call `setSystemTime` Again

**Date:** 2026-05-27
**Agent:** Coder (BRD-13 iter 2 — `ElapsedClock`)
**Category:** Frontend / Testing

### Situation
While testing a `setInterval`-driven `ElapsedClock`, the assertion `toHaveTextContent("3s")` reported the rendered value as `"6s"`. The test was:

```ts
vi.setSystemTime(new Date("00:00:00Z"));
render(<ElapsedClock startedAt="00:00:00Z" />);  // tick = 0
act(() => {
  vi.setSystemTime(new Date("00:00:03Z"));       // ← double-advance
  vi.advanceTimersByTime(3_000);                 // also advances Date
});
// expected 3s, got 6s
```

### Root Cause
`vi.advanceTimersByTime(ms)` already moves the fake clock forward by `ms` AND fires every timer whose deadline has passed during that window. Calling `setSystemTime(now + ms)` before `advanceTimersByTime(ms)` effectively jumps the clock twice: each interval tick calls `Date.now()`, which now returns `now + 2·ms`. The DOM ends up showing `2·ms` of elapsed time.

### Lesson
Use exactly one of the following per advance step:
- `vi.advanceTimersByTime(ms)` — moves the clock and fires timers (preferred for setInterval/setTimeout-driven UIs).
- `vi.setSystemTime(newDate)` — jumps the clock without firing timers (only when you want to observe an effect on the next render, not on the next tick).

Never call both back-to-back when measuring elapsed time. The fixture should use `advanceTimersByTime` exclusively.

### Prevention
- When writing fake-timer tests for clocks/animations, decide upfront: "does this assertion depend on timers firing?" If yes, only `advanceTimersByTime`.
- If a test needs a non-zero starting offset, call `setSystemTime` once **before** `render`, then drive elapsed time exclusively with `advanceTimersByTime`.

---

## L-008: Always Prefix Backend API Calls with `API_URL` — MANDATORY RULE

**Date:** 2026-05-26
**Agent:** All agents
**Category:** Frontend / Deployment

### Situation
`userStore.ts` called `fetch("/api/auth/register")` and `fetch("/api/auth/verify")` with a relative URL. In production (Vercel), these requests hit `https://novum-seven.vercel.app/api/...` instead of the real backend at `https://novum-prod.duckdns.org/api/...`, returning 404 or 405 errors. Other call sites (e.g. `lib/api.ts`, `lib/sse.ts`) correctly prefixed with `API_URL` and worked fine.

### Root Cause
The store was implemented before `lib/api.ts` was established, so it used raw `fetch` with a relative path. Relative paths work in development (Vite's dev proxy) but break in production where frontend and backend are on different origins.

### Lesson — NON-NEGOTIABLE RULE
**Every HTTP or SSE call to the backend MUST be prefixed with `API_URL` from `@/lib/constants`.**

```typescript
// ✅ CORRECT
import { API_URL } from "@/lib/constants";
fetch(`${API_URL}/api/auth/register`, { ... });

// ❌ WRONG — breaks in production (Vercel ≠ backend host)
fetch("/api/auth/register", { ... });
```

### Enforcement
1. Prefer `lib/api.ts` methods (`api.get`, `api.post`, etc.) — they already include `API_URL`.
2. If raw `fetch` is unavoidable (e.g. Zustand stores before `api.ts` existed), import `API_URL` explicitly and prefix the path.
3. SSE connections use `lib/sse.ts::createSSEConnection()` — it already prefixes with `API_URL`.
4. **Never use relative paths like `/api/...` for backend calls in any frontend file.**

### Prevention
- Code review checklist: search for `fetch("/"` or `fetch('/` in `frontend/src/` — any match is a bug candidate.
- ESLint rule (future): `no-restricted-syntax` on raw `fetch` calls without `API_URL`.

---

---

## L-007: Upgrading a Header-Only Auth Fixture Requires Touching All Downstream Route Tests

**Date:** 2026-05-26
**Agent:** Coder (BRD-04)
**Category:** Testing / FastAPI dependencies

### Situation
BRD-03 protected routes were guarded by a placeholder `get_current_username` that only inspected `X-Username`. The shared `seeded_user` fixture inserted a `User` with a sentinel `token_hash = "x" * 64`. When BRD-04 upgraded the dependency to also require `X-Token`, every test that previously sent only `X-Username` started returning 401, even though the implementation under test was the new auth dependency.

### Lesson
When the production identity contract changes, the fixtures that simulate identity must change in lockstep. Specifically:
- Replace the synthetic ORM insert with a real `AuthService.register(...)` call so the persisted `token_hash` matches a plain token you can hand out.
- Expose a sibling fixture (`auth_headers`) that returns the full `{X-Username, X-Token}` dict; never let downstream tests reconstruct the header pair by hand.
- Do a workspace-wide rewrite of `headers={"X-Username": seeded_user}` → `headers=auth_headers` in one pass; partial updates produce noisy 401 failures that look like new bugs.

### Prevention
For any future BRD that tightens an auth dependency:
1. Update the shared fixture first.
2. Run the full suite — every 401 is a candidate for the rewrite.
3. Add an explicit `test_get_current_username_*` matrix (missing headers / wrong token / unknown user / valid pair) so the dependency's contract is asserted directly, not only via side effects of other tests.

---

## L-006: `exactOptionalPropertyTypes` Requires `prop?: T | undefined` on Pass-Through Props

**Date:** 2026-05-26
**Agent:** Coder (BRD-11)
**Category:** Frontend / TypeScript

### Situation
`tsconfig.json` enables `exactOptionalPropertyTypes`. With that flag, declaring `className?: string` means the prop may be **omitted** but cannot be **passed as `string | undefined`**. `StatusBadge` accepted an optional `className?: string` and forwarded it to `Badge`, which broke `tsc` even though tests passed.

### Lesson
For any wrapper component that forwards an optional prop coming from its own props, declare the receiving prop as `prop?: T | undefined` (explicit `undefined`). Plain `prop?: T` only works when callers always omit the prop.

### Action
Changed `BadgeProps.className` from `string` to `string | undefined`. Apply the same pattern proactively to all forwarded optional props (`label`, `aria-*`, refs) in future atoms/molecules.

---

## L-005: SQLite Fallback for PG-Typed ORM Tests via `compiles`-hooks

**Date:** 2026-05-26
**Agent:** Coder (BRD-03)
**Category:** Testing / SQLAlchemy

### Situation
BRD-03 services exercise the production ORM (`Run`, `Event`) which uses PG-specific column types: `JSONB`, `UUID`, `ENUM`. Running tests against SQLite via `aiosqlite` fails at table creation because SQLite has no native equivalents.

### Resolution
Register `sqlalchemy.ext.compiler.compiles` hooks **only in the test fixture** that downgrade `JSONB → JSON`, `UUID → CHAR(36)`, `ENUM → VARCHAR` for the `sqlite` dialect. Production models stay untouched (architecture rule: storage is a not-seam).

```python
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, UUID, ENUM

@compiles(JSONB, "sqlite")
def _jsonb_sqlite(_t, _c, **_kw): return "JSON"
# ...
```

Combined with `StaticPool` + a session-scoped in-memory engine, the entire BRD-03 suite (108 tests) runs DB-free in <2s.

### When to reuse
- Any future BRD that touches the ORM (BRD-05+, BRD-07, BRD-15) and needs unit/integration tests without Postgres.
- Place the hook in a shared `tests/conftest.py` fixture; do **not** import it from production code.

### Caveats
- This does not validate PG-specific behaviour (JSONB operators, ENUM constraints). Migration-level tests under `pytest-postgresql` remain the ground truth (per L-004, L-003).

---

## L-004: Disable the `pytest-postgresql` Plugin When Running DB-Free Suites Locally

**Date:** 2026-05-26
**Agent:** Coder
**Category:** Testing

### What Happened
While verifying BRD-02 (pure-Python domain tests, no DB touched), the entire pytest collection aborted with `ImportError: no pq wrapper available` originating from `pytest_postgresql.plugin`. The plugin transitively imports `psycopg`, which the local venv has installed without `psycopg_binary` and without a system libpq DLL on PATH.

### Root Cause
`pytest-postgresql` is auto-loaded via the `pytest11` entry point. It runs at *collection* time, before any test code, so unrelated test files (e.g. domain unit tests) cannot opt out individually.

### Lesson Learned
For test runs that do not need PostgreSQL, pass `-p no:postgresql` to pytest:
```
pytest -q -p no:postgresql
```
This disables only the postgres plugin and leaves `pytest-asyncio`, `pytest-httpx`, etc., intact.

### Prevention
- Use `-p no:postgresql` in CI jobs and local commands that target DB-free suites.
- Long-term fix (not in BRD-02 scope): install `psycopg[binary]` in the dev group, or pin `psycopg-binary>=3.x` explicitly so the plugin's transitive dependency resolves on Windows.

### Applied To
- BRD-02 verification commands.

---

## L-003: Static-Only Tests for DB Migrations are Acceptable for Iteration 1

**Date:** 2026-05-26
**Agent:** Reviewer
**Category:** Testing Strategy

### What Happened
BRD-01 review (CR-01-001) considered whether to penalize the Coder for shipping migration tests that only inspect the module source instead of executing `alembic upgrade head` against a live or `pytest-postgresql` database. AC-01 and AC-05 were therefore only verified structurally.

### Decision
Static-only verification is acceptable for iteration 1 **when the BRD itself defers runtime verification to a later phase**. BRD-01 §7 explicitly marks integration testing as BRD-02 territory and `alembic upgrade head` as a manual P1 step. Penalizing the Coder here would amount to enforcing a stricter standard than the spec.

### Rule of Thumb
- If the BRD's "Testing Strategy" section defers a test type, treat its absence as Minor (advisory), never Major.
- If the BRD requires a test type and it is missing, treat its absence as Major or Blocker.
- Cheap source-substring tests (e.g., "does `downgrade()` mention every `drop_table` in reverse order?") are a free win and should be requested as Minors.

### Prevention
Reviewers must read the BRD's `Testing Strategy` section before scoring `Test Coverage`. Do not import the stricter standards of later BRDs retroactively.

---

## L-002: Unit Tests are Mandatory per F3.S3

**Date:** 2026-05-26
**Agent:** Orchestrator
**Category:** Process & Workflow

### What Happened
BRD-00 implementation was marked complete without unit tests. Review CR-00-001 passed at 9.4/10 but user flagged missing tests.

### Root Cause
Workflow step F3.S3 (`generate_unit_tests`) was skipped. The Coder (Orchestrator acting as Coder) focused on file structure setup and forgot that **every BRD implementation must include unit tests**.

### Lesson Learned
**Unit tests are NOT optional.** Per `workflow.md`:
- **F3.S3** explicitly requires: "Create unit tests (backend/frontend)"
- **Quality Standards** mandate: "Test Coverage ≥80%"
- Even setup/infrastructure BRDs need smoke tests to validate tooling works

For BRD-00 specifically:
- Backend: `test_health.py` — validates FastAPI health endpoint
- Frontend: `format.test.ts`, `clipboard.test.ts` — validates utility functions

### Prevention
Before marking any implementation complete:
1. ✅ Verify F3.S3 was executed
2. ✅ Run `pytest` (backend) and `vitest` (frontend)
3. ✅ Confirm tests pass before review submission

### Applied To
- BRD-00: Added missing unit tests
- All future BRDs: F3.S3 is mandatory

---

## L-001: BRD Template for Spec-Driven Development

**Date:** 2026-05-26
**Agent:** BSA Agent
**Category:** Process & Workflow

### What Happened
Creating implementation specs for Novum project. Needed a BRD format that enables Copilot to implement directly from specifications without ambiguity.

### Root Cause
Standard BRD templates are too abstract for AI-assisted coding. Generic descriptions like "implement authentication" don't provide enough detail for automated implementation.

### Lesson Learned
BRDs optimized for Copilot need:
- **Implementation Order** field for sequencing
- **Exact file paths** in File Structure section
- **Copy-paste ready code blocks** (SQL, Python, TypeScript)
- **Alembic migration templates** included inline
- **UI ASCII mockups** for layout specs
- **Implementation Checklist** with specific file paths

### Prevention
Always use the enhanced BRD template at `.github/memory-bank/templates/brd-template.md` for all future specs.

### Applied To
- All 19 BRDs for Novum V1 implementation

---

## Categories

### Bugs & Debugging
_None yet._

### Performance
_None yet._

### Architecture
_None yet._

### Process & Workflow
_None yet._

### Testing
_None yet._

### Documentation
_None yet._

---

## Template

When adding a new lesson, use this format:

```markdown
## L-{number}: {Title}

**Date:** {YYYY-MM-DD}
**Agent:** {agent name}
**Category:** Bugs | Performance | Architecture | Process | Testing | Documentation

### What Happened
{Describe the situation that led to this lesson}

### Root Cause
{What was the underlying cause?}

### Lesson Learned
{What did we learn from this?}

### Prevention
{How do we prevent this in the future?}

### Applied To
- {Where was this lesson applied?}

---
```

---

## How to Add Lessons

1. Increment the lesson number (L-001, L-002, etc.)
2. Fill out the template completely
3. Update the "Total Lessons" count above
4. Add to the appropriate category section
5. Update the "Recent Lessons" section (keep last 5)

---

## Lesson Triggers

Add a lesson when:
- A bug takes more than 30 minutes to resolve
- A code review finds a significant issue
- An architectural decision needs to be revised
- A test fails unexpectedly
- A deployment fails
- A misunderstanding causes rework
- A better approach is discovered after implementation


---

---

## L-018 — Anchor TLD subdomain regexes with `(^|\.)` (2026-05-28, IP-23 Phase 3)

**Context:** Authority tiering classifier matched `foogov.uk` and `notgov.uk` as primary-authoritative because the regex was `gov\.uk$` without a subdomain anchor.

**Lesson:** When matching a TLD-style suffix that is only authoritative when it appears as its own subdomain (`gov.uk`, `ac.uk`, `co.jp`, …), the regex MUST be `(^|\.)gov\.uk$` — never the bare `gov\.uk$`. The leading `(^|\.)` requires either the very start of the host string or a literal dot before the suffix.

**Counter-example to avoid:**

```python
# WRONG — matches foogov.uk
re.search(r"gov\.uk$", host)

# RIGHT
re.search(r"(^|\.)gov\.uk$", host)
```

**Mini-test pattern:**

```python
for bad in ["foogov.uk", "notgov.uk", "pseudogov.uk"]:
    assert classify_authority(f"https://{bad}/x") is not AuthorityTier.PRIMARY_AUTHORITATIVE

for good in ["gov.uk", "cabinet.gov.uk", "dwp.gov.uk"]:
    assert classify_authority(f"https://{good}/x") is AuthorityTier.PRIMARY_AUTHORITATIVE
```

**Applies to:** any TLD/suffix matcher in `backend/app/sources/authority.py` and any future seam that relies on host-suffix matching.
