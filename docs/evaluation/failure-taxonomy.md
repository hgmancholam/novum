# Failure Taxonomy — Novum Agent Runs

Canonical classification for every non-`judge_confirmed` run. Owned by the EvalEngineer agent. Extend rows, never collapse them.

> **Usage:** Every entry in `iteration-history-*.md` tags each failing question with one **primary** category (F-XXX-YYY) and zero-or-more **secondary** tags. Trends across iterations expose where to invest (planner vs judge vs retrieval vs synthesis).

## Categories

| Code                       | Category                            | Trigger condition                                                                                          | Typical fix locus                                          |
|----------------------------|-------------------------------------|------------------------------------------------------------------------------------------------------------|------------------------------------------------------------|
| **F-PLAN-OVERCLAIM**       | Planner over-decomposed             | `claim_count > CLAIM_BUDGETS[(qtype, complexity)]`                                                         | `backend/app/agent/tasks/plan.py` budgets                  |
| **F-PLAN-UNDERCLAIM**      | Planner under-decomposed            | `judge.missing_evidence != []` AND `coverage < 0.6`                                                       | planner prompt                                             |
| **F-RETRIEVE-SPARSE**      | Search returned <2 sources / claim  | `evidence_per_claim < 2`                                                                                  | source plugins / retrieve round config                     |
| **F-RETRIEVE-OFFTOPIC**    | Evidence retrieved but not on-topic | `last_agreement < 0.5` AND `evidence_count >= 4`                                                          | reranking / planner query phrasing                         |
| **F-JUDGE-TESTY**          | Judge testy on completeness         | `S >= 0.6` AND `passed=false` AND `not contradictions_detected`                                           | structural override thresholds; judge model swap (last resort) |
| **F-JUDGE-FALSEPOSITIVE**  | Judge passed on weak evidence       | `passed=true` AND `coverage < 0.4` (requires manual review to confirm)                                    | judge prompt / threshold                                   |
| **F-SYNTH-VERBOSE**        | Draft over BL strict length         | extracted prose > 25w (Q1-Q6) or > 40w (Q7-Q8)                                                            | synthesizer prompt                                         |
| **F-SYNTH-HEDGED**         | Excess hedging vs evidence support  | LLM-rubric hedging score (meta-judge)                                                                     | synthesizer prompt                                         |
| **F-STOP-OVERSHOOT**       | Budget exhausted while progressing  | `evidence_delta_last_round > 0` AND `stop_reason = stopped_by_budget`                                     | budget config / saturation signal                          |
| **F-COST-BLOAT**           | Cost > 2× type median               | `CostIncurredEvent.total_usd > 2 * median(type)`                                                          | model routing / round cap                                  |

## Cross-Reference to RFs

| Category                | Related RF                                              |
|-------------------------|---------------------------------------------------------|
| F-PLAN-*                | RF-06 (planner), RF-11 (sub-claims)                     |
| F-RETRIEVE-*            | RF-04 (source heterogeneity), RF-07 (retrieval)         |
| F-JUDGE-*               | RF-12 (confidence formula), RF-02 (stop reasons)        |
| F-SYNTH-*               | RF-13 (UI honesty), RF-17 (answer kind)                 |
| F-STOP-OVERSHOOT        | RF-02 (stop reasons), RF-09 (budget signals)            |
| F-COST-BLOAT            | RF-16 (cost)                                            |

## Trend Tracker (updated per iteration)

| Iteration | Total runs | judge_confirmed | F-PLAN-* | F-RETRIEVE-* | F-JUDGE-* | F-SYNTH-* | F-STOP-* | F-COST-* |
|-----------|:----------:|:---------------:|:--------:|:------------:|:---------:|:---------:|:--------:|:--------:|
| postux    | 8          | 2               | -        | -            | -         | 7 verbose | -        | -        |
| postq     | 8          | 2               | -        | -            | 6 testy   | 1 verbose | -        | -        |
| postj     | 8          | 2               | 0 (capped) | -          | 6 testy   | 2 verbose | -        | -        |
| postov    | 8          | 3 (Q4 flipped)  | 0        | -            | 3 testy (Q5,Q7,Q8 blocked by coverage/agreement) | 2 verbose | -        | -        |
| postinst  | (pending IP-38 instrumentation) | | | | | | | |
