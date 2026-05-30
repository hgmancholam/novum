# Eval Instrumentation Skill

## Description
Add minimal-cost, no-schema-migration telemetry to the Novum event stream so behavioral changes become observable. Used by EvalEngineer (P2 — *instrument before tune*) and by Coder when prepping an IP-XX-instr precursor diff.

## When to Use
- Before changing any agent/orchestrator/scoring threshold whose effect is currently invisible to `compare_*.py`.
- When a `compare_*.py` report shows fields as `None` or `-`.
- When a hypothesis names a metric not yet emitted by any event.

## Non-Goals
- **Not** a place to add new event types lightly. Prefer `extra="allow"` on the closest existing event.
- **Not** for FE-visible fields — extras are stripped by the generated TS types.
- **Not** for cost-tracking (use `CostIncurredEvent` directly).

## Core Pattern — Attach Extras to Existing Events

`BaseEvent` declares `model_config = ConfigDict(extra="allow")`. This means you can attach arbitrary fields to any event subclass at construction or post-hoc:

```python
# Good — attach at construction
judge_event = await evaluate_with_judge(state, emit_event=self.emit)
coverage = calculate_coverage(state)
agreement = calculate_agreement(state.evidence, expected_experts=state.expected_experts or None)
# Stash for IP-38 override telemetry (extra="allow" — no schema change)
judge_event.coverage = coverage
judge_event.agreement = agreement
judge_event.override_eligible = (
    not judge_event.passed
    and not judge_event.contradictions_detected
    and judge_event.structural_confidence >= 0.6
    and coverage >= 0.6
    and agreement >= 0.5
)
judge_event.override_blockers = [
    name for name, ok in [
        ("structural", judge_event.structural_confidence >= 0.6),
        ("coverage",   coverage >= 0.6),
        ("agreement",  agreement >= 0.5),
        ("contradictions", not judge_event.contradictions_detected),
    ] if not ok
]
await self.emit(judge_event)
```

After `model_dump()`, the extras land in the `payload JSONB` column and are queryable via:

```sql
SELECT
  run_id,
  payload->>'override_eligible'    AS eligible,
  payload->>'override_blockers'    AS blockers,
  (payload->>'coverage')::float    AS coverage,
  (payload->>'agreement')::float   AS agreement,
  (payload->>'structural_confidence')::float AS s
FROM events
WHERE event_type = 'judge_ruled'
  AND run_id = ANY(:run_ids);
```

## When a New Event IS Justified

Add a new `*Evaluated` event only when **all** of the following hold:
- The decision is taken at a point where no existing event is being emitted.
- The decision is independent of any existing event's lifecycle (e.g. override that may or may not fire after JudgeRuled).
- You need it indexed (frequent queries) — JSONB extras are queryable but not indexed by default.

If you add one, update:
- `app/domain/events.py` — class + add to union + add to EventType enum + add to `EventType → class` map
- `app/agent/orchestrator.py` (or call site) — emit it
- `scripts/export_types.py` (FE types regeneration, only if FE consumes it — usually NO for eval-only events)
- Tests covering its emission
- `tests/fixtures/runs/*.jsonl` golden traces if affected

## Compare-Script Pattern

The compare scripts in `scripts/compare_*.py` follow this shape:

```python
def _fetch_judge_telemetry(conn, run_id):
    rows = conn.execute("""
        SELECT
          payload->>'passed' AS passed,
          (payload->>'structural_confidence')::float AS s,
          (payload->>'coverage')::float AS coverage,
          (payload->>'agreement')::float AS agreement,
          payload->>'override_eligible' AS override_eligible,
          payload->>'override_blockers' AS override_blockers
        FROM events
        WHERE run_id = %s AND event_type = 'judge_ruled'
        ORDER BY ts ASC LIMIT 1
    """, (run_id,)).fetchone()
    return rows or {}
```

The report should always show:
- Per-question: `S | coverage | agreement | override_eligible | blockers`
- Aggregate: of the runs where `override_eligible=true`, how many flipped to `judge_confirmed`? If <100%, instrumentation is incomplete OR the override has a bug.

## Stats Helpers (for n=small)

For n≤25, raw counts mislead. Use `scripts/eval_stats/bootstrap.py`:

```python
def bootstrap_ci(samples: list[float], n_iter: int = 1000, ci: float = 0.9) -> tuple[float, float]:
    """Non-parametric bootstrap CI for the mean of a small sample."""
    import random
    means = []
    for _ in range(n_iter):
        resample = [random.choice(samples) for _ in samples]
        means.append(sum(resample) / len(resample))
    means.sort()
    lo_idx = int(((1 - ci) / 2) * n_iter)
    hi_idx = int((1 - (1 - ci) / 2) * n_iter)
    return means[lo_idx], means[hi_idx]

def sign_test_p(deltas: list[float]) -> float:
    """One-sided sign test: P(≥k positives | binomial(n, 0.5))."""
    from math import comb
    positives = sum(1 for d in deltas if d > 0)
    n = sum(1 for d in deltas if d != 0)
    if n == 0:
        return 1.0
    return sum(comb(n, k) for k in range(positives, n + 1)) / (2 ** n)
```

Report `delta_ci=[lo, hi]` and `sign_test_p=p` next to every aggregate metric.

## Checklist (mandatory before claiming "instrumented")

- [ ] Extras land in `payload JSONB` (verified via `SELECT` on the events table).
- [ ] `compare_<tag>.py` reads and reports the new field for every Q in the golden set.
- [ ] No FE type regeneration needed (or, if needed, types regen'd and FE compiled).
- [ ] Unit test added asserting the field is non-`None` when expected (e.g. after a `JUDGING` transition).
- [ ] No regression on existing `pytest` suite.
