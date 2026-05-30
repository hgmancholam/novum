"""Compare IP-39 (postcontra) vs IP-38 (postinst) baselines.

IP-39 hypothesis primary metric:
  Q4 (S=0.94, cov=1.0, agr=1.0, ev=57) MUST flip stopped_by_budget -> judge_confirmed
  via the high-confidence contradictions bypass.

Secondary floors (no regression vs postinst):
  - judge_confirmed >= 3/8
  - BL strict >= 6/8
  - wallclock avg <= 130s
  - contra_bypassed fires only on runs with S>=0.85 AND agr>=0.9 AND ev>=5
    (must NOT fire on weak runs like Q3 zero-evidence)

Reuses fetch/summarize/parse logic from compare_postinst (imported).
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compare_postinst import fetch_set, parse_eval_log  # noqa: E402

# IP-38 (postinst) baseline — Q4=budget (the regression target IP-39 must fix).
POSTINST = [
    ("Q1", "ac156e91-5120-4410-9f2f-7b40452fdf2a", 22.9),
    ("Q2", "68daa970-6ff8-495f-94ab-079b6b10f231", 45.3),
    ("Q3", "b613ac05-965b-47a6-a96c-43c5cbbb6f8a", 39.6),
    ("Q4", "586b0ef2-5ba4-465a-8f23-9ea28fb14728", 145.8),
    ("Q5", "0401d6a5-6e93-4631-8f8b-01658c34a1d3", 116.6),
    ("Q6", "d6ab8ceb-7e4d-4af5-8f5d-7cd2ee028983", 106.6),
    ("Q7", "48ea4cb9-7287-4697-ae72-8dbfebe202cf", 114.2),
    ("Q8", "fd5a84a8-4c86-417a-9b6f-97b9f4644eec", 83.8),
]


def main() -> int:
    postcontra = parse_eval_log(Path("eval_postcontra.txt"))
    if not postcontra:
        print("ERROR: eval_postcontra.txt not found or empty.", file=sys.stderr)
        return 1
    print(f"[parsed] {len(postcontra)} run_ids from eval_postcontra.txt")

    new = fetch_set("postcontra (IP-39)", postcontra)
    old = fetch_set("postinst (IP-38 baseline)", POSTINST)

    by_label_old = {r["label"]: r for r in old}

    # ------------------------------------------------------------
    # PRIMARY: Q4 flip
    # ------------------------------------------------------------
    print("\n=== IP-39 PRIMARY METRIC — Q4 flip ===")
    q4_old = by_label_old.get("Q4", {})
    q4_new = next((r for r in new if r["label"] == "Q4"), {})
    q4_old_reason = q4_old.get("stop_reason", "?")
    q4_new_reason = q4_new.get("stop_reason", "?")
    q4_flip_ok = (q4_old_reason == "stopped_by_budget" and q4_new_reason == "judge_confirmed")
    print(f"  Q4 postinst: {q4_old_reason}")
    print(f"  Q4 postcontra: {q4_new_reason}  {'PASS' if q4_flip_ok else 'FAIL'}")
    print(f"  Q4 contra_bypassed flag: {q4_new.get('contra_bypassed')}")

    # ------------------------------------------------------------
    # SECONDARY: floors
    # ------------------------------------------------------------
    def stop_count(rows): return Counter(r.get("stop_reason") for r in rows if "error" not in r)
    a, b = stop_count(old), stop_count(new)
    keys = sorted(set(a) | set(b))
    print("\n=== STOP REASON FLOOR (postinst baseline) ===")
    print(f"  {'reason':25} {'postinst':>10} {'postcontra':>12}")
    for k in keys:
        print(f"  {k:25} {a.get(k, 0):>10} {b.get(k, 0):>12}")
    jc_old = a.get("judge_confirmed", 0)
    jc_new = b.get("judge_confirmed", 0)
    jc_floor_ok = jc_new >= jc_old
    print(f"\n  judge_confirmed: postinst={jc_old} postcontra={jc_new}  "
          f"{'PASS' if jc_floor_ok else 'FAIL'}")

    bl_old = sum(1 for r in old if not r.get("error") and r.get("bl_strict_ok"))
    bl_new = sum(1 for r in new if not r.get("error") and r.get("bl_strict_ok"))
    bl_floor_ok = bl_new >= 6
    print(f"  BL strict: postinst={bl_old}/8 postcontra={bl_new}/8  "
          f"{'PASS' if bl_floor_ok else 'FAIL'} (floor=6)")

    walls_new = [r.get("wallclock_s") or 0 for r in new if not r.get("error")]
    avg_wall = sum(walls_new) / max(len(walls_new), 1)
    wall_ok = avg_wall <= 130
    print(f"  wallclock_avg: {avg_wall:.0f}s  "
          f"{'PASS' if wall_ok else 'FAIL'} (ceiling=130s)")

    # ------------------------------------------------------------
    # BYPASS DISCIPLINE: only fires on legit runs
    # ------------------------------------------------------------
    print("\n=== CONTRA-BYPASS DISCIPLINE ===")
    bypass_violations = []
    for r in new:
        if r.get("error"):
            continue
        bp = r.get("contra_bypassed")
        s = r.get("S") or 0.0
        agr = r.get("agreement") or 0.0
        ev = r.get("evidence_total") or 0
        if bp:
            ok = (s >= 0.85 and agr >= 0.9 and ev >= 5)
            mark = "OK" if ok else "VIOLATION"
            print(f"  {r['label']:3} bypassed=YES S={s:.2f} agr={agr:.2f} ev={ev}  {mark}")
            if not ok:
                bypass_violations.append(r["label"])
    bypass_ok = not bypass_violations
    if not [r for r in new if r.get("contra_bypassed")]:
        print("  (no bypass fired — Q4 should have triggered it)")

    # ------------------------------------------------------------
    # PER QUESTION
    # ------------------------------------------------------------
    print("\n=== PER QUESTION (postcontra, IP-39) ===")
    for r in new:
        if "error" in r:
            print(f"  {r['label']:3} ERROR {r['error']}")
            continue
        cov = '-' if r['coverage'] is None else f"{r['coverage']:.2f}"
        agr = '-' if r['agreement'] is None else f"{r['agreement']:.2f}"
        s = '-' if r['S'] is None else f"{r['S']:.2f}"
        bp = '*' if r.get('contra_bypassed') else '.'
        print(
            f"  {r['label']:3} {str(r['route'] or '-'):9} "
            f"{str(r['stop_reason'] or '-')[:22]:22} "
            f"S={s:>5} cov={cov:>5} agr={agr:>5} bypass={bp} "
            f"ev={r['evidence_total']:>3} h={r['unique_hosts']:>2} "
            f"BL25={'y' if r['bl_strict_ok'] else '.'}({r['bl_word_count']:>2}w) "
            f"t={(r['wallclock_s'] or 0):.0f}s"
        )

    # ------------------------------------------------------------
    # PER-Q DIFF — postinst vs postcontra (prompt + answer quality)
    # ------------------------------------------------------------
    print("\n=== PER-Q DIFF (postinst -> postcontra) ===")
    quality_regressions: list[str] = []
    for r in new:
        if r.get("error"):
            continue
        lbl = r["label"]
        o = by_label_old.get(lbl, {})
        q = (r.get("question_text") or o.get("question_text") or "")[:90]
        print(f"\n  [{lbl}] {q}")
        print(f"     stop      : {o.get('stop_reason','-'):22} -> {r.get('stop_reason','-')}")
        print(f"     S/J/conf  : {o.get('S')}/{o.get('J')}/{o.get('conf')}  ->  "
              f"{r.get('S')}/{r.get('J')}/{r.get('conf')}")
        print(f"     ev/hosts  : {o.get('evidence_total',0)}/{o.get('unique_hosts',0)}  ->  "
              f"{r.get('evidence_total',0)}/{r.get('unique_hosts',0)}")
        old_w, new_w = o.get("answer_words", 0), r.get("answer_words", 0)
        old_c = o.get("citation_count", 0) or 0
        new_c = r.get("citation_count", 0) or 0
        delta_pct = ((new_w - old_w) / old_w * 100) if old_w else 0
        print(f"     answer_w  : {old_w} -> {new_w} ({delta_pct:+.0f}%)  cites: {old_c} -> {new_c}")
        old_hosts = set((o.get("host_counter") or {}).keys())
        new_hosts = set((r.get("host_counter") or {}).keys())
        overlap = len(old_hosts & new_hosts) / max(len(old_hosts | new_hosts), 1) * 100
        print(f"     host_jaccard: {overlap:.0f}%   (old∩new={len(old_hosts & new_hosts)})")
        # Regression heuristics: answer shrank >40% OR cites dropped >40% OR hosts overlap <30% on confirmed runs
        if old_w >= 50 and new_w < old_w * 0.6:
            quality_regressions.append(f"{lbl}:answer-shrank({old_w}->{new_w})")
        if old_c >= 3 and new_c < old_c * 0.6:
            quality_regressions.append(f"{lbl}:cites-dropped({old_c}->{new_c})")
        if old_hosts and overlap < 30 and r.get("stop_reason") == o.get("stop_reason"):
            quality_regressions.append(f"{lbl}:host-shift({overlap:.0f}%)")

    quality_ok = not quality_regressions
    print(f"\n  quality_regressions: {quality_regressions or 'none'}  "
          f"{'PASS' if quality_ok else 'WARN'}")

    # ------------------------------------------------------------
    # FULL ANSWERS DUMP — for human eyeballing (truncated to 500 ch)
    # ------------------------------------------------------------
    print("\n=== FULL ANSWERS (postcontra, 500ch) ===")
    for r in new:
        if r.get("error"):
            continue
        print(f"\n  [{r['label']}] Q: {(r.get('question_text') or '')[:120]}")
        a = (r.get("answer_full") or "").strip().replace("\n", " ")
        print(f"     A: {a[:500]}{'...' if len(a) > 500 else ''}")

    # ------------------------------------------------------------
    # VERDICT
    # ------------------------------------------------------------
    print("\n=== IP-39 VERDICT ===")
    print(f"  Q4_flip            {'PASS' if q4_flip_ok else 'FAIL'}")
    print(f"  judge_confirmed    {'PASS' if jc_floor_ok else 'FAIL'}")
    print(f"  BL_strict          {'PASS' if bl_floor_ok else 'FAIL'}")
    print(f"  wallclock_avg      {'PASS' if wall_ok else 'FAIL'}")
    print(f"  bypass_discipline  {'PASS' if bypass_ok else 'FAIL'} "
          f"{'(violations: ' + ','.join(bypass_violations) + ')' if bypass_violations else ''}")
    print(f"  quality (advisory) {'PASS' if quality_ok else 'WARN — ' + ','.join(quality_regressions)}")
    verdict = "PASS" if (q4_flip_ok and jc_floor_ok and bl_floor_ok and wall_ok and bypass_ok) else "FAIL"
    print(f"  >>> VERDICT: {verdict}   (quality is advisory, does not gate)")

    Path("compare_postcontra.json").write_text(
        json.dumps(
            {"postcontra": new, "postinst": old, "verdict": verdict,
             "q4_flip": q4_flip_ok, "bypass_violations": bypass_violations,
             "quality_regressions": quality_regressions},
            indent=2,
        ),
        encoding="utf-8",
    )
    print("\n[done] wrote compare_postcontra.json")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
