# IP-21 — Status Audit (post-implementation)

**Audited:** 2026-05-27
**Plan:** [IP-21 — "Always Answer" Refactor](../implementation-plans/IP-21-always-answer-refactor.md)
**Auditor:** Orchestrator (post-hoc reconciliation against `git log`)
**Result:** ✅ **All 7 work packages landed.** No implementation work pending. Documentation log was lagging behind code; this audit + the new entries in `decisions-history.md` close the gap.

---

## 1. WP-by-WP traceability

| WP | Scope (per plan) | Status | Landing commit(s) |
|----|------------------|--------|-------------------|
| **WP-0** | Reconciliation — re-create `select_answer_kind.py`, fix 5 pre-existing failing tests, repo green | ✅ landed | `b716ef4` |
| **WP-1** | Additive prelude — AnswerKind resolver + matrix tests | ✅ landed | `b716ef4` |
| **WP-2** | Six synthesizer templates + ambiguity wiring (G3) + contradiction surfacing (G10) | ✅ landed | `8459f16`, `9ef6800` (stabilization, 33 regressions → 0) |
| **WP-2.0** | Classifier prompt extension (8 `QuestionType` values, G9 empty-comparative) | ✅ landed | `8459f16` |
| **WP-2.5** | Contradiction detector contract — `analyze_evidence()` groups by claim+stance, emits `ContradictionDetectedEvent` | ✅ landed | `8459f16` |
| **WP-3** | `StopReason` 7 → 4 collapse, Alembic 002, kind-aware structural confidence, early-stop G8, `StopRationale`, FE `honest_*` removal, G13 resolver acceptance matrix | ✅ landed | `6ec6f39` |
| **WP-4** | Saturation novelty signal + in-memory embeddings + budget audit | ✅ landed | `f27abd4`, `afc0009` |
| **WP-5** | Independent verifier extension — judge returns coherence / contradictions / missing_evidence (Anthropic Haiku path) | ✅ landed | `f27abd4`, `afc0009` |
| **WP-6** | Cross-run question memory (in-memory) with `PriorRunHint` isolation | ✅ landed | `f27abd4`, `c47f322` (settings-casing prod-crash fix) |

EventType count is now **22** (was 17 pre-IP-21); FE/BE type contract regenerated via `scripts/export_types.py` (commit `840f9b3`).

---

## 2. Post-WP-6 hardening series (not in original plan)

These commits address issues surfaced by smoke runs against `novum.duckdns.org` and are **legitimately scope-of-IP-21** (the plan binds smoke matrix §0.8 as the acceptance contract):

| Commit | Theme | Why it was needed |
|--------|-------|-------------------|
| `955b5d2` | `settings.*` lowercase normalization + `_RawSynthesizerPayload` wrapper | Production crashed on every saturation eval; `instructor` rejects `response_model=dict`. |
| `b767234` | Surface draft on `STOPPED_BY_BUDGET`; `key_points` optional | "Always answer" promise was being broken when budget exhausted before judge passed. |
| `f461d9f` | Wire `detect_empty_comparative` + resolver reorder | Empty-comparative + ambiguity must precede type priority for matrix row 3 (`"best programming language?"`). |
| `cf1bc8b` | `SourcesCard` FE organism | RF-13 trust-surfacing for evidence sources. |
| `bddb050` | Rotate across N GitHub PATs per call | Smoke run 6 hit `Too many requests` on 7/8 questions (single-token quota collapse). |
| `840f9b3` | Typed `StructuredAnswerData` payload + native FE rendering | Replaces markdown-only rendering; new `StructuredBlocks` organism. |
| `63c8670` | Intra-call token fallback on `RateLimitError` | Walk the PAT pool inline before tenacity backoff. |
| `38f681b` | Synthesizer payload coercion + retry on `ValidationError` | LLM emits `citations=None`, stringified `remaining_uncertainties`, dict-shaped `key_points` — coerce before validation; prevents spurious `stop_reason=errored`. |
| `7b70418` | Smoke SSE timeout 600s → 1500s | Q2 / Q3 legitimately need ~18 min to hit `max_rounds=20`. |
| `8b48650` | `UsernameModal` glass-strong variant | Visual polish — cosmetic. |
| `e497e85` | PAT smoke-test script | Dev tooling for the PAT rotation feature. |

---

## 3. Smoke matrix (IP-21 §0.8) — last known state

The matrix (8 questions → expected `AnswerKind` + capabilities) is the binding acceptance contract. Latest smoke runs persisted under `smoke_ip21_run*.txt` in the repo root and `frontend/vitest_*.txt` for the FE side.

The G13 static enforcement (`backend/tests/test_resolver_acceptance.py`) is in place and gates every commit. The smoke dynamic runs are gated behind manual execution (rate-limit budget).

---

## 4. Open items (none for IP-21)

- No WP from the plan is missing.
- No "TODO" left from any decision entry.
- Documentation lag closed by this audit + the `D-WP-3`, `D-WP-4-5-6`, `D-WP-POST` entries appended to `decisions-history.md`.

If a regression in any matrix row appears post-smoke, the fix is **out of scope of IP-21** — open a new IP per plan rule §0.8.

---

## 5. Recovery note

The chat session that drove WP-3..WP-6 (`213b4a15`) lost its `.jsonl` request log. Tool outputs were recovered to [`session-213b4a15-recovered.md`](../session-213b4a15-recovered.md). That file is informational only — all decisions it implies were already enacted in the commits listed above.
