# US-22-3: Expected expert profiles + agreement credibility multiplier

**Story ID:** US-22-3
**Title:** Planner declares `expected_experts`; `analyze_evidence` boosts agreement weight of expert-matched sources
**BRD Reference:** BRD-22
**Priority:** Medium
**Estimated Effort:** M
**Status:** Draft (F1 — awaiting Auditor)

---

## User Story

**As a** research-agent orchestrator
**I want** the planner to declare the type of experts whose sources should be most trusted for a given question, and `analyze_evidence` to give those sources a small credibility boost (1.1×) when they appear in agreement calculation
**So that** authoritative domains (e.g. `mayoclinic.org` for a nutrition question, `arxiv.org` for an AI-research question) tilt agreement toward better-grounded answers without overriding the existing `min(S_effective, J)` invariant or compounding multiple expert matches

---

## Acceptance Criteria

### Scenario 1: Planner emits matching experts for a fact question
```gherkin
Given question "What is the capital of Japan?" classified as factual/trivial
When create_plan runs
Then PlanCreatedEvent.expected_experts == ["encyclopedia", "geographer"]
```

### Scenario 2: Planner emits matching experts for a health question
```gherkin
Given question "Is intermittent fasting safe for women over 40?"
When create_plan runs
Then PlanCreatedEvent.expected_experts contains "nutritionist"
And  PlanCreatedEvent.expected_experts contains "medical_researcher"
```

### Scenario 3: Agreement boost applies when source domain matches expert
```gherkin
Given a plan with expected_experts == ["nutritionist", "medical_researcher"]
And  evidence row E with source_url "https://www.mayoclinic.org/healthy-lifestyle/..." and base agreement contribution 0.50
When calculate_agreement runs with expected_experts
Then E's weighted contribution equals 0.55  (0.50 × 1.1, clamped to [0,1])
```

### Scenario 4: No multiplier when no expert matches
```gherkin
Given a plan with expected_experts == ["database_engineer"]
And  evidence row E with source_url "https://www.mayoclinic.org/..." (no DB-engineer match)
When calculate_agreement runs
Then E's weighted contribution equals 0.50 (unchanged)
```

### Scenario 5: Multiplier does NOT compound
```gherkin
Given a plan with expected_experts == ["nutritionist", "medical_researcher"]
And  evidence row E with source_url "https://www.mayoclinic.org/..." matching BOTH experts
When calculate_agreement runs
Then the applied multiplier is exactly 1.1  (NOT 1.1 × 1.1 == 1.21)
```

### Scenario 6: Multiplier clamps at 1.0
```gherkin
Given evidence row E with base contribution 0.95 and a matching expert
When calculate_agreement runs
Then E's weighted contribution is min(0.95 × 1.1, 1.0) == 1.0
```

### Scenario 7: Multiplier preserves the confidence formula shape
```gherkin
Given a run completes with expert-boosted agreement
When final_confidence is computed
Then final_confidence == min(S_effective, J)
And  S_effective == S_raw × kind_ceiling[answer_kind]
And  the multiplier appears inside S_raw via agreement; never modifies kind_ceiling or J
```

### Scenario 8: Replay of pre-BRD-22 plan tolerates missing `expected_experts`
```gherkin
Given a historical PlanCreatedEvent without expected_experts
When the orchestrator replays it
Then no validation error is raised
And  calculate_agreement runs with expected_experts == None
And  no multiplier is applied (all rows multiplier = 1.0)
```

### Scenario 9: Unknown expert label is ignored, not raised
```gherkin
Given a plan with expected_experts == ["alien_anthropologist"]  // not in taxonomy
When calculate_agreement runs
Then no multiplier is applied to any evidence row
And  a structured log "expert_label_unknown label=alien_anthropologist" is recorded
And  no exception is raised
```

---

## Technical Notes

### Backend Considerations
- New module `app/agent/experts/taxonomy.py` shipping the static `expert_taxonomy: dict[str, list[str]]` (full table in Appendix A).
- Domain matching: by **exact suffix** on the registered hostname (no path, no query). Strip `www.` before matching. TLD-family rules (e.g. `*.gov`, `*.edu`) match on suffix of the full TLD chain.
- `match(source_domain: str, expected_experts: list[str] | None) -> float` returns `1.1` or `1.0`. Defined in `app/agent/experts/taxonomy.py`.
- `calculate_agreement(evidence, expected_experts=None)` — new optional kwarg, default `None`. Threaded through `analyze_evidence`.
- Multiplier applied **per evidence row, once**, then clamped to `[0.0, 1.0]`. Never accumulates.
- Planner-side: `create_plan` extracts `expected_experts` from the planner LLM output. Prompt is extended to request the field; existing `PlanOutput` Pydantic model adds `expected_experts: list[str] | None = None`.
- Language policy: all identifiers and log messages English.

### Frontend Considerations
- New molecule `ExpectedExpertsList.tsx` rendering `["Looking for sources from:", "nutritionist", "medical_researcher"]` as readable chips in the plan card.
- `scripts/export_types.py` regenerates `events.ts`.

### Database Changes
- None.

### API Changes
- None.

---

## UI/UX Notes

- Microcopy: header `"Looking for sources from:"`. Each expert label rendered title-cased and underscore-stripped: `"Medical Researcher"`, `"Database Engineer"`.
- Render in Center Panel `C5` planning state, right below `ComplexityBadge`.
- a11y: `<ul role="list">` with `aria-label="Expected expert types for this plan"`.

---

## Dependencies

- [ ] BRD-22 approved (F1)
- [ ] US-22-1 merged (`ComplexityHint`)
- [ ] US-22-2 merged (`PlanCreatedEvent` already extended with optional fields)
- [ ] BRD-08 (confidence calculation) — `calculate_agreement` exists

---

## Test Cases

| ID | Test Description | Type | Priority |
|---|---|---|---|
| TC-01 | `match("mayoclinic.org", ["nutritionist"]) == 1.1` | Unit | High |
| TC-02 | `match("mayoclinic.org", ["database_engineer"]) == 1.0` | Unit | High |
| TC-03 | `match("blog.example.com", ["nutritionist"]) == 1.0` | Unit | High |
| TC-04 | TLD-family rule: `match("nih.gov", ["medical_researcher"]) == 1.1` via `*.gov` | Unit | High |
| TC-05 | Two matching experts → still 1.1 (no compounding) | Unit | High |
| TC-06 | Multiplier clamps at 1.0 | Unit | High |
| TC-07 | `expected_experts=None` → all multipliers = 1.0 | Unit | High |
| TC-08 | Unknown label → log + no raise | Unit | Medium |
| TC-09 | Integration: end-to-end agreement uplift on a synthetic 3-evidence run | Integration | High |
| TC-10 | Confidence invariant `min(S_effective, J)` preserved | Integration | High |
| TC-11 | FE: `ExpectedExpertsList` renders + jest-axe green | Unit | Medium |

Test files: `backend/tests/test_experts_taxonomy.py` (TC-01..08), `backend/tests/test_agreement_expert_boost.py` (TC-09, TC-10), `frontend/src/components/molecules/ExpectedExpertsList.test.tsx` (TC-11).

---

## Definition of Done

- [ ] `app/agent/experts/taxonomy.py` exists with ≥ 10 expert types covering ≥ 30 domain patterns (see Appendix A)
- [ ] `match()` helper exists and is pure / deterministic
- [ ] `calculate_agreement` accepts `expected_experts` kwarg and applies the 1.1× multiplier with clamp + no compounding
- [ ] `PlanCreatedEvent.expected_experts` populated by `create_plan`
- [ ] Planner prompt extended to request the field
- [ ] `backend/tests/test_experts_taxonomy.py` + `test_agreement_expert_boost.py` green
- [ ] FE types regenerated
- [ ] `ExpectedExpertsList.tsx` + test exist, a11y green
- [ ] Coverage ≥ 80 %
- [ ] Reviewer score ≥ 9 / 10
- [ ] Memory bank updated

---

## Appendix A — Initial `expert_taxonomy` contract

This dictionary is the V1 ship-with-code taxonomy. **Static.** Edits = code change + new BRD entry.

```python
# app/agent/experts/taxonomy.py
expert_taxonomy: dict[str, list[str]] = {
    "encyclopedia": [
        "wikipedia.org",
        "britannica.com",
        "encyclopedia.com",
    ],
    "geographer": [
        "nationalgeographic.com",
        "cia.gov",          # World Factbook
        "*.gov",            # generic gov authority for geography
    ],
    "nutritionist": [
        "mayoclinic.org",
        "eatright.org",
        "nutrition.org",
        "harvard.edu",      # T.H. Chan school of public health
    ],
    "medical_researcher": [
        "nih.gov",
        "pubmed.ncbi.nlm.nih.gov",
        "who.int",
        "thelancet.com",
        "nejm.org",
        "*.edu",            # academic medicine
    ],
    "database_engineer": [
        "postgresql.org",
        "mongodb.com",
        "use-the-index-luke.com",
        "martinfowler.com",
        "highscalability.com",
    ],
    "saas_architect": [
        "aws.amazon.com",
        "cloud.google.com",
        "azure.microsoft.com",
        "stripe.com",
        "vercel.com",
    ],
    "software_engineer": [
        "stackoverflow.com",
        "github.com",
        "developer.mozilla.org",
        "infoq.com",
        "thoughtworks.com",
    ],
    "academic_researcher": [
        "arxiv.org",
        "scholar.google.com",
        "acm.org",
        "ieee.org",
        "nature.com",
        "science.org",
        "*.edu",
    ],
    "industry_analyst": [
        "gartner.com",
        "forrester.com",
        "mckinsey.com",
        "bcg.com",
        "deloitte.com",
    ],
    "legal_scholar": [
        "law.cornell.edu",
        "scotusblog.com",
        "*.gov",
        "europa.eu",
    ],
    "economist": [
        "imf.org",
        "worldbank.org",
        "oecd.org",
        "federalreserve.gov",
        "ecb.europa.eu",
    ],
    "journalist": [
        "reuters.com",
        "apnews.com",
        "bbc.com",
        "ft.com",
        "wsj.com",
    ],
}
```

**Coverage:** 12 expert types, 50 distinct domain patterns (≥ 10 expert types + ≥ 30 patterns as required by BRD-22).

**Matching rules (formal):**
1. Normalise: lowercase, strip leading `www.`, drop path / query.
2. For each expert in `expected_experts`, scan its pattern list.
3. Pattern starting with `*.` matches any host whose TLD chain ends with the suffix (e.g. `*.gov` matches `nih.gov` and `cia.gov`).
4. Other patterns match by exact suffix (e.g. `mayoclinic.org` matches `www.mayoclinic.org` and `health.mayoclinic.org`).
5. First match wins; multiplier is `1.1` and is NOT re-applied for further matches in the same evidence row.

---

## Document History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | 2026-05-27 | BSA Agent | Initial creation (F1) — taxonomy seeded with 12 experts × 50 domains |
