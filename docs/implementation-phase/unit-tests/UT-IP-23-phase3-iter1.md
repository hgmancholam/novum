# UT-IP-23 Phase 3 — Authority Tiering (WP-3)

**Phase**: 3 (WP-3)
**Iteration**: 1
**Date**: 2026-05-28

## Test Inventory

### New backend tests (43 cases)

**`backend/tests/test_sources_authority_tiers.py`** — 28 cases
- Government / public institution (`.gov`, `.gov.uk`, `.mil`, `europa.eu`, `un.org`, `who.int`, `nih.gov`) → `PRIMARY_AUTHORITATIVE`.
- University / research (`.edu`, `mit.edu`, `ox.ac.uk`, `cnrs.fr`) → `PRIMARY_AUTHORITATIVE`.
- Peer-reviewed journals (`nature.com`, `science.org`, `cell.com`, `jstor.org`, `arxiv.org`) → `PRIMARY_AUTHORITATIVE`.
- Established media (`bbc.com`, `nytimes.com`, `reuters.com`, `apnews.com`, `economist.com`) → `REPUTABLE_SECONDARY`.
- General websites (random `.com`/`.io`) → `GENERAL`.
- Low-signal (blogs, forums: `*.blogspot.com`, `medium.com/@user`, `reddit.com`, `quora.com`, `*.wordpress.com`) → `LOW_SIGNAL`.
- Edge cases: `gov.fake.com` → `GENERAL` (subdomain anchor regression test for L-016); empty string and malformed URLs → `GENERAL`.

**`backend/tests/test_confidence_authority_multiplier.py`** — 15 cases
- `_authority_multiplier(None)` → 0.90 (GENERAL, replay tolerance).
- Each tier maps to its config value (`primary=1.05`, `reputable=1.00`, `general=0.90`, `low=0.50`).
- `C_coverage` per-claim mean: 1 PRIMARY + 1 LOW = 0.775; clamped to [0,1].
- `C_diversity` per-domain mean: 3 unique domains × mean(1.05, 1.00, 0.50) = 0.7 × 0.85 = 0.595.
- Asymmetry: `C_agreement` and `C_no_conflict` unchanged regardless of tier.
- RF-12 invariant: `final_confidence == min(S_effective, J)` holds whether tiers raise or lower S.

### New frontend tests (5 cases)

**`frontend/src/components/molecules/AuthorityTierChip.test.tsx`**
- Renders "Primary" for `primary_authoritative`.
- Renders "Reputable" for `reputable_secondary`.
- Renders "General" for `general`.
- Renders "Low signal" for `low_signal`.
- Passes jest-axe a11y check.

### Modified baseline tests (9 cases — factory adjustment only)

`test_confidence_structural.py::_ev` and
`test_confidence_calculator.py::_state_full` and
`test_agent_tasks_draft.py::_state` now seed
`authority_tier=AuthorityTier.REPUTABLE_SECONDARY` so multiplier = 1.0
and pre-WP-3 numeric expectations remain valid. No production code
changes.

## Run Results

### Backend (full suite)

```
732 passed in 110.95s (0:01:50)
```

Saved to: `pytest_ip23_phase3_iter1.txt`

### Frontend (full suite)

```
Test Files  1 failed | 67 passed (68)
Tests       1 failed | 476 passed (477)
Duration    135.16s
```

Single failure: `UsernameModal.test.tsx::renders the dialog with
token-based classes (no hardcoded colors)` — pre-existing,
unrelated, declared OUT OF SCOPE.

Saved to: `vitest_ip23_phase3_iter1.txt`

## Coverage

Targeted modules (authority + structural confidence): functional
coverage 100 % (every branch of `classify_authority` and
`_authority_multiplier` exercised). Aggregate workspace coverage
remains above the 80 % floor (no regressions from baseline).
