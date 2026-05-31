"""Compare IP-40 (postIP40, instrumentation-only) vs IP-39 (postcontra).

IP-40 is a READ-ONLY iteration: no behavioral change. The diagnostic
snapshot embedded in JudgeRuled extras should pinpoint WHY
coverage = 0 on 3-claim plans (Q5, Q6, Q8) despite ample evidence.

Primary metric:
  Bug class localized for Q5 / Q6 / Q8 — one of:
    A: sub_claims show 'covered' but `coverage` is 0  -> calculate_coverage bug
    B: sub_claims show 'pending' despite evidence ≥2  -> analyze_evidence bug
    C: state.evidence empty at judge time             -> state reset bug
    D: evidence routed to '<none>' or alien claim_ids -> routing bug

Secondary floors (no regression vs postcontra):
  - judge_confirmed >= 2/8
  - BL strict >= 6/8
  - wallclock avg <= 130s
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compare_postinst import fetch_events, fetch_set, parse_eval_log  # noqa: E402

# IP-39 (postcontra) baseline.
POSTCONTRA = [
    ("Q1", "5b0c35c6-6efb-4b6f-a89b-86a4cf72d3c5", 17.0),
    ("Q2", "67fecf12-12c4-4bc0-9263-46bdc63b0d2f", 66.0),
    ("Q3", "34888004-9d10-4afd-93ab-a44ad6c33ba2", 45.0),
    ("Q4", "0a046c57-1d3c-43fc-8b24-68588bbe0730", 130.0),
    ("Q5", "24987fd3-5767-4edf-88c4-26e7041707f6", 118.0),
    ("Q6", "b3f8761a-2b5f-43d6-9f54-a6dbc83fcf91", 105.0),
    ("Q7", "2ef1e2cd-d2b2-4ce5-a4c8-3a4f74b3ec43", 112.0),
    ("Q8", "208a7c9b-bce0-4ff9-8b8a-7e6e60c5e74e", 101.0),
]

# Multi-claim plans were the bug locus in postcontra.
DIAG_TARGETS = {"Q5", "Q6", "Q8"}


def _classify_bug(diag: dict, evidence_total: int) -> tuple[str, str]:
    """Classify the coverage=0 root cause from the IP-40 diagnostic block.

    Returns (class_letter, evidence_summary).
    """
    sub_claims = diag.get("diag_sub_claims") or []
    covered_ids = set(diag.get("diag_covered_claim_ids") or [])
    ev_per_claim = diag.get("diag_evidence_per_claim") or {}

    if not sub_claims:
        return ("?", "no diag_sub_claims (instrumentation not deployed?)")

    sub_ids = {c["id"] for c in sub_claims}
    pending = [c for c in sub_claims if c["status"] == "pending"]
    covered = [c for c in sub_claims if c["status"] == "covered"]

    ev_routed_to_unknown = sum(
        v for k, v in ev_per_claim.items() if k == "<none>" or k not in sub_ids
    )
    total_routed = sum(ev_per_claim.values())

    # CLASS C: state.evidence empty at judge time
    if total_routed == 0 and evidence_total > 0:
        return ("C", f"events show {evidence_total} ev but state.evidence empty at judge")

    # CLASS D: routing bug — significant evidence to '<none>' or alien ids
    if total_routed > 0 and ev_routed_to_unknown / total_routed > 0.3:
        return ("D", f"{ev_routed_to_unknown}/{total_routed} ev routed to <none>/alien ids")

    # CLASS A: sub_claims covered but coverage is 0 — happens upstream of judge
    if covered and len(covered_ids) > 0:
        return ("A", f"covered_ids={sorted(covered_ids)} but coverage=0 -> calculate_coverage bug")

    # CLASS B: pending despite enough evidence
    pending_with_ev = []
    for c in pending:
        n = ev_per_claim.get(c["id"], 0)
        if n >= 2:
            pending_with_ev.append((c["id"], n))
    if pending_with_ev:
        details = ", ".join(f"{cid}:{n}ev" for cid, n in pending_with_ev)
        return ("B", f"pending despite evidence: {details} -> analyze_evidence not running/broken")

    return ("?", f"sub_claims={[(c['id'],c['status']) for c in sub_claims]} "
                 f"ev_per_claim={ev_per_claim}")


def _extract_diag(run_id: str) -> dict:
    """Pull diag_* fields from the LAST JudgeRuled event of a run."""
    events = fetch_events(run_id)
    judge_events = [e for e in events if e.get("event") == "JudgeRuled"]
    if not judge_events:
        return {}
    last = judge_events[-1].get("data", {})
    return {k: v for k, v in last.items() if k.startswith("diag_")}


def main() -> int:
    postIP40 = parse_eval_log(Path("eval_postIP40.txt"))
    if not postIP40:
        print("ERROR: eval_postIP40.txt not found or empty.", file=sys.stderr)
        return 1
    print(f"[parsed] {len(postIP40)} run_ids from eval_postIP40.txt")

    new = fetch_set("postIP40 (instrumentation)", postIP40)
    old = fetch_set("postcontra (IP-39 baseline)", POSTCONTRA)

    by_label_old = {r["label"]: r for r in old}

    # ------------------------------------------------------------
    # PRIMARY: coverage diagnostic for Q5/Q6/Q8
    # ------------------------------------------------------------
    print("\n=== IP-40 PRIMARY — coverage=0 bug localization ===")
    bug_classes: dict[str, str] = {}
    diag_present = False
    for label in sorted(DIAG_TARGETS):
        row = next((r for r in new if r["label"] == label), None)
        if row is None or row.get("error"):
            print(f"  {label}: skipped (no run)")
            continue
        diag = _extract_diag(row["run_id"])
        if any(k.startswith("diag_") for k in diag):
            diag_present = True
        ev_total = row.get("evidence_total") or 0
        klass, summary = _classify_bug(diag, ev_total)
        bug_classes[label] = klass
        print(f"\n  [{label}] coverage={row.get('coverage')} S={row.get('S'):.2f} ev={ev_total}")
        print(f"     diag_sub_claims      : {diag.get('diag_sub_claims')}")
        print(f"     diag_covered_claim_ids: {diag.get('diag_covered_claim_ids')}")
        print(f"     diag_evidence_per_claim: {diag.get('diag_evidence_per_claim')}")
        print(f"     diag_search_count     : {diag.get('diag_search_count')}")
        print(f"     >>> CLASS {klass}: {summary}")

    primary_ok = diag_present and all(c != "?" for c in bug_classes.values())
    print(f"\n  instrumentation_deployed: {'YES' if diag_present else 'NO'}")
    print(f"  bug classes: {bug_classes}")
    print(f"  PRIMARY: {'PASS — bug class identified' if primary_ok else 'FAIL — diagnostic inconclusive'}")

    # ------------------------------------------------------------
    # SECONDARY FLOORS (no regression vs postcontra)
    # ------------------------------------------------------------
    def stop_count(rows): return Counter(r.get("stop_reason") for r in rows if "error" not in r)
    a, b = stop_count(old), stop_count(new)
    keys = sorted(set(a) | set(b))
    print("\n=== STOP REASON FLOOR (postcontra baseline) ===")
    print(f"  {'reason':25} {'postcontra':>12} {'postIP40':>10}")
    for k in keys:
        print(f"  {k:25} {a.get(k, 0):>12} {b.get(k, 0):>10}")
    jc_old = a.get("judge_confirmed", 0)
    jc_new = b.get("judge_confirmed", 0)
    jc_floor_ok = jc_new >= 2
    print(f"\n  judge_confirmed: postcontra={jc_old} postIP40={jc_new}  "
          f"{'PASS' if jc_floor_ok else 'FAIL'} (floor=2)")

    bl_old = sum(1 for r in old if not r.get("error") and r.get("bl_strict_ok"))
    bl_new = sum(1 for r in new if not r.get("error") and r.get("bl_strict_ok"))
    bl_floor_ok = bl_new >= 6
    print(f"  BL strict: postcontra={bl_old}/8 postIP40={bl_new}/8  "
          f"{'PASS' if bl_floor_ok else 'FAIL'} (floor=6)")

    walls_new = [r.get("wallclock_s") or 0 for r in new if not r.get("error")]
    avg_wall = sum(walls_new) / max(len(walls_new), 1)
    wall_ok = avg_wall <= 130
    print(f"  wallclock_avg: {avg_wall:.0f}s  "
          f"{'PASS' if wall_ok else 'FAIL'} (ceiling=130s)")

    # ------------------------------------------------------------
    # PER QUESTION
    # ------------------------------------------------------------
    print("\n=== PER QUESTION (postIP40) ===")
    for r in new:
        if "error" in r:
            print(f"  {r['label']:3} ERROR {r['error']}")
            continue
        cov = '-' if r['coverage'] is None else f"{r['coverage']:.2f}"
        agr = '-' if r['agreement'] is None else f"{r['agreement']:.2f}"
        s = '-' if r['S'] is None else f"{r['S']:.2f}"
        print(
            f"  {r['label']:3} {str(r['route'] or '-'):9} "
            f"{str(r['stop_reason'] or '-')[:22]:22} "
            f"S={s:>5} cov={cov:>5} agr={agr:>5} "
            f"ev={r['evidence_total']:>3} h={r['unique_hosts']:>2} "
            f"BL25={'y' if r['bl_strict_ok'] else '.'}({r['bl_word_count']:>2}w) "
            f"t={(r['wallclock_s'] or 0):.0f}s"
        )

    # ------------------------------------------------------------
    # PER-Q DIFF (postcontra -> postIP40)
    # ------------------------------------------------------------
    print("\n=== PER-Q DIFF (postcontra -> postIP40) ===")
    for r in new:
        if r.get("error"):
            continue
        lbl = r["label"]
        o = by_label_old.get(lbl, {})
        q = (r.get("question_text") or o.get("question_text") or "")[:90]
        print(f"\n  [{lbl}] {q}")
        print(f"     stop: {o.get('stop_reason','-'):22} -> {r.get('stop_reason','-')}")
        print(f"     S/J: {o.get('S')}/{o.get('J')}  ->  {r.get('S')}/{r.get('J')}")
        print(f"     ev/hosts: {o.get('evidence_total',0)}/{o.get('unique_hosts',0)}  ->  "
              f"{r.get('evidence_total',0)}/{r.get('unique_hosts',0)}")
        print(f"     answer_w: {o.get('answer_words',0)} -> {r.get('answer_words',0)}  "
              f"cites: {o.get('citation_count',0)} -> {r.get('citation_count',0)}")

    # ------------------------------------------------------------
    # VERDICT
    # ------------------------------------------------------------
    print("\n=== IP-40 VERDICT ===")
    print(f"  primary (bug class)  {'PASS' if primary_ok else 'FAIL'}")
    print(f"  judge_confirmed      {'PASS' if jc_floor_ok else 'FAIL'}")
    print(f"  BL_strict            {'PASS' if bl_floor_ok else 'FAIL'}")
    print(f"  wallclock_avg        {'PASS' if wall_ok else 'FAIL'}")
    verdict = "PASS" if (primary_ok and jc_floor_ok and bl_floor_ok and wall_ok) else "FAIL"
    print(f"  >>> VERDICT: {verdict}")
    print(f"\n  >>> NEXT IP (IP-41): fix the bug class(es) {sorted(set(bug_classes.values()) - {'?'})}")

    Path("compare_postIP40.json").write_text(
        json.dumps(
            {"postIP40": new, "postcontra": old, "verdict": verdict,
             "bug_classes": bug_classes, "primary_ok": primary_ok},
            indent=2,
        ),
        encoding="utf-8",
    )
    print("\n[done] wrote compare_postIP40.json")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
