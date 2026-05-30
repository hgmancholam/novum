# Implementation Plan — IP-30: Classifier `domain` field & domain-aware source routing

**Plan ID:** IP-30
**Parent BRD:** *(BRD-30 to be authored alongside; this plan documents the contract change)*
**Date:** 2026-05-30
**Author:** Pair-session
**Complexity:** M (standard) — `quality_profiles.M`, model tier `balanced`
**Estimated Effort:** ~120 LOC + 6 tests (≈ 2-3 h pair-session)
**Iteration:** 1

---

## 1. Plan summary

IP-30 adds **one closed-enum field** (`domain`) to the classifier output and threads it through `build_source_hints()` so the four Source plugins can specialise per academic discipline / web vertical. Three concrete behaviours land in this plan:

1. **S2 / OpenAlex** map `domain` → `fieldsOfStudy` (S2) and `fieldsOfStudy` (OpenAlex). This becomes the **primary** mapping; the existing `expected_experts` mapping stays as fallback when `domain == "other"` or unmapped.
2. **Tavily** auto-injects an `include_domains` allowlist of authoritative sites per domain — **only when** the caller did not pass `include_domains` AND `complexity_hint != "deep"` (DEEP needs source diversity for the judge).
3. **Search cascade** ([`backend/app/agent/tasks/search.py`](../../../backend/app/agent/tasks/search.py)) skips S2 and OpenAlex when `domain ∈ {geopolitics, lifestyle, history}` — there is no academic literature to surface and the calls return `[]` 95% of the time, wasting latency and tokens.

The change is strictly **additive** at the contract boundary: new optional field on `QuestionClassification`, new optional field on `QuestionClassifiedEvent` (`extra="allow"` already in place per RF-03), default `"other"` so historical event payloads validate unchanged.

### Out of scope (deferred to later plans)
- Geographic scope (`geo_scope`) — separate plan IP-31.
- Min-citation count is **already shipped** (commit on 2026-05-30, see [`backend/app/sources/semantic_scholar.py`](../../../backend/app/sources/semantic_scholar.py) `minCitationCount` block).
- Tavily `include_domains` for DEEP lane — explicitly skipped to preserve judge diversity guarantees.
- Per-domain prompt tweaks for the synthesizer — current synthesizer prompts stay domain-agnostic.

---

## 2. Contract changes

### 2.1 New enum

`backend/app/domain/enums.py` (new):

```python
class QuestionDomain(str, Enum):
    """Closed taxonomy emitted by the classifier (IP-30).

    Drives source-plugin specialisation (fieldsOfStudy, include_domains)
    and cascade skipping. Default is OTHER so pre-IP-30 events validate.
    """
    MEDICAL = "medical"
    LEGAL = "legal"
    FINANCIAL = "financial"
    TECHNOLOGY = "technology"        # consumer tech, hardware, infra
    SCIENCE = "science"              # natural sciences, physics, chem, bio
    GEOPOLITICS = "geopolitics"
    BUSINESS = "business"
    HISTORY = "history"
    EDUCATION = "education"
    LIFESTYLE = "lifestyle"
    SOFTWARE_ENGINEERING = "software_engineering"
    OTHER = "other"
```

### 2.2 Pydantic model

`backend/app/llm/models.py::QuestionClassification`:

```python
domain: QuestionDomain = Field(
    default=QuestionDomain.OTHER,
    description="Topical domain — drives source plugin specialisation (IP-30)",
)
```

### 2.3 Event

`backend/app/domain/events.py::QuestionClassifiedEvent`:

```python
domain: QuestionDomain | None = None  # IP-30 (additive per RF-03)
```

### 2.4 Run state

`backend/app/agent/run_state.py::RunState`:

```python
domain: QuestionDomain | None = None
```

### 2.5 Hint surface

`backend/app/agent/source_hints.py::build_source_hints` adds:

```python
"domain": state.domain.value if state.domain else None,
```

---

## 3. Phase breakdown

> Single phase — change is too small to justify splitting. Tasks ordered so each one compiles & tests green standalone.

### Task T-30-01 — Enum + Pydantic model + event field

| File | Change |
|---|---|
| [`backend/app/domain/enums.py`](../../../backend/app/domain/enums.py) | Add `QuestionDomain` enum (12 values). |
| [`backend/app/llm/models.py`](../../../backend/app/llm/models.py) | Add `domain: QuestionDomain = QuestionDomain.OTHER` to `QuestionClassification`. |
| [`backend/app/domain/events.py`](../../../backend/app/domain/events.py) | Add `domain: QuestionDomain \| None = None` to `QuestionClassifiedEvent`. |
| [`backend/app/agent/run_state.py`](../../../backend/app/agent/run_state.py) | Add `domain: QuestionDomain \| None = None`. |

**Tag:** [backend] [types]
**Effort:** XS (~25 LOC)

### Task T-30-02 — Classifier prompt update

| File | Change |
|---|---|
| [`backend/app/llm/prompts.py`](../../../backend/app/llm/prompts.py) | Extend `CLASSIFIER_SYSTEM_PROMPT` with the 12-domain closed list and the output-schema line `\`domain\` (string, one of the 12 values above)`. |

Exact prompt addition (English, per language-policy memory):

```
Domains (pick exactly one — closed list):
- medical — clinical care, drugs, diseases, public health
- legal — laws, regulations, court cases, compliance
- financial — markets, banking, taxes, investment
- technology — consumer tech, hardware, infrastructure
- science — natural sciences (physics, chemistry, biology, earth sciences)
- geopolitics — international relations, wars, sanctions, diplomacy
- business — companies, management, strategy, marketing
- history — pre-2000 events, biographies, archaeology
- education — pedagogy, curricula, learning theory
- lifestyle — food, travel, fitness, hobbies, relationships
- software_engineering — programming languages, frameworks, architecture patterns, software design
- other — anything that does not fit above

Rules for `domain`:
- When the question spans two domains (e.g. "how does inflation affect mental health?"), pick the domain of the *outcome* the user is asking about (here: medical).
- Only use `other` when no domain above plausibly fits.
```

Append to the schema spec section:
```
- `domain` (string, one of the 12 values above in lowercase snake_case)
```

**Tag:** [backend]
**Effort:** S (~30 LOC of prompt)

### Task T-30-03 — Orchestrator wires `domain` into state + event

| File | Change |
|---|---|
| [`backend/app/agent/orchestrator.py`](../../../backend/app/agent/orchestrator.py) | After `classify_question(...)`, set `self.state.domain = verdict.domain` (mirroring the existing `complexity_hint` / `temporal_sensitivity` pattern). Pass `domain=verdict.domain` to `QuestionClassifiedEvent(...)`. |

**Tag:** [backend]
**Effort:** XS (~6 LOC)

### Task T-30-04 — `build_source_hints` emits `domain`

| File | Change |
|---|---|
| [`backend/app/agent/source_hints.py`](../../../backend/app/agent/source_hints.py) | Add `"domain": state.domain.value if state.domain else None` to the returned dict. |

**Tag:** [backend]
**Effort:** XS (~3 LOC)

### Task T-30-05 — S2 consumes `domain`

| File | Change |
|---|---|
| [`backend/app/sources/semantic_scholar.py`](../../../backend/app/sources/semantic_scholar.py) | Add `_DOMAIN_TO_S2_FIELDS: dict[str, list[str]]` (table below). In `search()`, **before** the `expected_experts` block, look up `domain` hint; if mapped, set `params["fieldsOfStudy"]` from it. Only fall back to `expected_experts` mapping when `domain` is `None`, `"other"`, or unmapped. |

```python
_DOMAIN_TO_S2_FIELDS: dict[str, list[str]] = {
    "medical":              ["Medicine", "Biology"],
    "science":              ["Physics", "Chemistry", "Biology", "Geology", "Environmental Science"],
    "technology":           ["Computer Science", "Engineering"],
    "software_engineering": ["Computer Science"],
    "financial":            ["Economics", "Business"],
    "business":             ["Business", "Economics"],
    "legal":                ["Law", "Political Science"],
    "geopolitics":          ["Political Science", "Sociology"],
    "education":            ["Education", "Psychology"],
    "history":              ["History"],
    # lifestyle, other → no mapping (let S2 search across all fields)
}
```

**Tag:** [backend]
**Effort:** S (~20 LOC)

### Task T-30-06 — OpenAlex consumes `domain`

| File | Change |
|---|---|
| [`backend/app/sources/openalex.py`](../../../backend/app/sources/openalex.py) | Same pattern as S2: `_DOMAIN_TO_OPENALEX_CONCEPTS` map (table below). Append `concepts.id:<id>` filter when mapped. OpenAlex concepts are **opaque IDs** (e.g. `C71924100` = Medicine) — list at top of file with a comment pointing to https://api.openalex.org/concepts. |

```python
# OpenAlex top-level concept IDs (https://api.openalex.org/concepts?filter=level:0)
_DOMAIN_TO_OPENALEX_CONCEPTS: dict[str, str] = {
    "medical":              "C71924100",   # Medicine
    "science":              "C121332964",  # Physics  (most common parent; biology/chem ride along via OR not needed at level 0)
    "technology":           "C41008148",   # Computer science
    "software_engineering": "C41008148",
    "financial":            "C162324750",  # Economics
    "business":             "C144133560",  # Business
    "legal":                "C17744445",   # Political science  (Law is sub-level; PolSci is the closest level-0 anchor)
    "geopolitics":          "C17744445",
    "education":            "C145420912",  # Education
    "history":              "C95457728",   # History
}
```

**Tag:** [backend]
**Effort:** S (~25 LOC)

### Task T-30-07 — Tavily consumes `domain` (FAST/STANDARD only)

| File | Change |
|---|---|
| [`backend/app/sources/tavily.py`](../../../backend/app/sources/tavily.py) | Add `_DOMAIN_TO_INCLUDE_DOMAINS` table. In `search()`, **after** checking explicit `include_domains` hint, if none provided AND `complexity_hint != "deep"` AND `domain` is mapped, set `include_domains` to the allowlist. |

```python
# Authoritative domain allowlists per topical domain. Applied only when the
# caller did not pass include_domains AND complexity_hint is not "deep" —
# DEEP needs source diversity to feed the judge. Lists kept short (~5-7
# hosts) to leave room for organic results.
_DOMAIN_TO_INCLUDE_DOMAINS: dict[str, list[str]] = {
    "medical":     ["nih.gov", "who.int", "cdc.gov", "nature.com", "thelancet.com", "mayoclinic.org", "nejm.org"],
    "legal":       ["supremecourt.gov", "eur-lex.europa.eu", "loc.gov", "law.cornell.edu", "echr.coe.int"],
    "financial":   ["sec.gov", "federalreserve.gov", "imf.org", "worldbank.org", "bis.org", "ecb.europa.eu"],
    "geopolitics": ["un.org", "oecd.org", "cfr.org", "rand.org", "brookings.edu", "chathamhouse.org"],
    "science":     ["nature.com", "science.org", "pnas.org", "sciencedirect.com"],
    # technology / software_engineering / business / history / education / lifestyle
    # → keep open web (no curated allowlist gives lift here)
}
```

**Tag:** [backend]
**Effort:** S (~20 LOC)

### Task T-30-08 — Cascade skips academic sources for non-academic domains

| File | Change |
|---|---|
| [`backend/app/agent/tasks/search.py`](../../../backend/app/agent/tasks/search.py) | Inside `_search_one_claim`, before the cascade loop, if `state.domain.value in {"geopolitics", "lifestyle", "history"}`, filter out `SourceType.SEMANTIC_SCHOLAR` and `SourceType.OPENALEX` from the local copy of `cascade`. Emit a `structlog.debug` line `cascade_skipped_academic_sources` for trace visibility. |

**Tag:** [backend]
**Effort:** XS (~10 LOC)

### Task T-30-09 — Type export

| File | Change |
|---|---|
| [`frontend/src/types/events.ts`](../../../frontend/src/types/events.ts) | Regenerate via `python scripts/export_types.py`. Verify `domain` appears on `QuestionClassifiedEvent`. |

**Tag:** [types]
**Effort:** XS (regenerated file, no manual edit)

---

## 4. Test plan

| Test file | Test name | Verifies | New / Modified |
|---|---|---|---|
| `backend/tests/test_classifier_domain.py` | `test_classifier_emits_domain_for_each_canonical_question` (parametrised: 5 question stems → expected domain, with stubbed LLM) | Prompt elicits correct domain | NEW |
| `backend/tests/test_classifier_domain.py` | `test_classifier_defaults_to_other_on_missing_field` (LLM returns no `domain` key → validation tolerates default) | Backward compatibility | NEW |
| `backend/tests/test_agent_source_hints.py` | `test_build_source_hints_emits_domain` | Hints propagation | NEW |
| `backend/tests/test_sources_semantic_scholar.py` | `test_search_maps_domain_to_fields_of_study` | T-30-05 | NEW |
| `backend/tests/test_sources_semantic_scholar.py` | `test_search_prefers_domain_over_expected_experts` (both passed → domain wins) | T-30-05 fallback rule | NEW |
| `backend/tests/test_sources_openalex.py` | `test_search_maps_domain_to_concepts_filter` | T-30-06 | NEW |
| `backend/tests/test_sources_tavily.py` | `test_search_applies_domain_allowlist_when_no_include_domains` | T-30-07 | NEW |
| `backend/tests/test_sources_tavily.py` | `test_search_skips_domain_allowlist_on_deep_complexity` | T-30-07 guard | NEW |
| `backend/tests/test_sources_tavily.py` | `test_search_explicit_include_domains_wins_over_domain_allowlist` | T-30-07 precedence | NEW |
| `backend/tests/test_agent_tasks_search.py` | `test_cascade_skips_academic_sources_for_geopolitics` | T-30-08 | NEW |
| `backend/tests/test_agent_tasks_search.py` | `test_cascade_keeps_academic_sources_for_other_domain` | T-30-08 inverse | NEW |
| `backend/tests/test_domain_events.py` | `test_question_classified_event_accepts_domain` (and validates against the enum) | Schema compat | MODIFIED |
| `backend/tests/test_domain_events.py` | `test_question_classified_event_replays_without_domain` (legacy payload) | RF-03 | MODIFIED |

**Coverage gate:** `pytest --cov=app.sources --cov=app.agent.source_hints --cov=app.agent.tasks.search --cov-fail-under=80`.

---

## 5. Risks & mitigations

| # | Risk | Likelihood | Mitigation |
|---|------|------------|------------|
| R-30-01 | Classifier LLM ignores the new `domain` instruction and returns malformed JSON | Low | Pydantic default `OTHER` absorbs missing field; instructor's structured output retries handle malformed values. |
| R-30-02 | `_DOMAIN_TO_INCLUDE_DOMAINS` allowlist is too restrictive → Tavily returns `[]` and dead-ends cascade (same bug class as the recent `_search_one_claim` empty-results bug) | Medium | (a) Already fixed: empty results no longer break cascade. (b) Skip allowlist for DEEP. (c) Lists kept to ~5-7 authoritative hosts that index broadly. (d) Monitor first 24 h of prod runs; if `Tavily → []` rate spikes for any single domain, prune that allowlist entry. |
| R-30-03 | Cascade skip drops legitimate academic results for borderline domains (e.g. `geopolitics` question that has good OpenAlex coverage) | Low | Skip list is conservative (only 3 of 12 domains). Question-author can override by manually re-asking with different phrasing → classifier picks different domain. Acceptable for V1. |
| R-30-04 | Mis-classification of `domain` cascades into wrong source mix | Medium | Default `OTHER` triggers no specialisation → graceful degradation to current behaviour. Tests parametrise 5+ stems per domain. |
| R-30-05 | OpenAlex concept IDs drift / get renamed | Very Low | OpenAlex concept IDs are stable per their docs. If one is removed, the source returns `[]` for that filter and cascade falls through. |
| R-30-06 | Frontend `events.ts` becomes stale because `export_types.py` is not run | Low | Pre-commit hook already runs the export for `schema/` changes; CI fails if `events.ts` diff is unstaged. |

---

## 6. Rollout & verification

1. Land all 9 tasks in **one PR** (feature is small enough; phased rollout adds no value).
2. After merge, run the local 8-question smoke matrix (`scripts/run_eval_2026_05_29.py` or its successor) and diff:
   - Per-question `domain` value (new column).
   - Tavily `include_domains` populated count.
   - S2 / OpenAlex `fieldsOfStudy` / `concepts` count.
   - Cascade skips for geopolitics/lifestyle/history questions.
3. Manual spot-check: 2 questions per domain (24 total) confirming the `domain` value matches editorial judgment.
4. If any `_DOMAIN_TO_INCLUDE_DOMAINS` entry causes >50% empty-result rate on Tavily during smoke, prune that entry before tagging the release.

---

## 7. Open questions for the user

| # | Question | Default if not answered |
|---|---|---|
| Q-30-1 | Should `software_engineering` and `technology` collapse into one domain? They share the same S2 / OpenAlex mapping today. | Keep separate — they diverge on Tavily allowlist intent (stackoverflow.com vs. arstechnica.com) in future iterations. |
| Q-30-2 | Should `history` cascade-skip S2/OpenAlex, or keep them (historical scholarship has academic literature)? | Skip — empirical evidence from prod shows historical questions get >90% empty S2 results, but reversible if we observe lost recall. |
| Q-30-3 | Should `domain` also re-prioritise `preferred_sources` (e.g. medical → wikipedia first because of the curated `Medical Reference` infoboxes)? | Out of scope for IP-30. Stays as a future refinement. |

---

## 8. Done criteria

- [ ] All 9 tasks merged in `main`.
- [ ] All new + modified tests green.
- [ ] `pytest backend/tests/ -q` total green, no regressions.
- [ ] Coverage ≥ 80% on `app/sources/*.py` and `app/agent/source_hints.py`.
- [ ] Frontend `events.ts` regenerated and committed.
- [ ] Smoke matrix run; per-domain counts logged.
- [ ] One commit per task or one squash commit per phase (decided by reviewer).
