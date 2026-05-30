"""Compare IP-38 (postinst, instrumented JudgeRuled) vs IP-37 (postov) vs IP-36 (postj).

IP-38 is a PURE INSTRUMENTATION diff (no behavioral change). This script
demonstrates the new fields are queryable from events.payload:
  - coverage, agreement (from JudgeRuled extras)
  - override_eligible (bool) — would the IP-37 structural override fire?
  - override_blockers (list[str]) — which of {structural,coverage,agreement,contradictions} blocked it

POSTINST run_ids must be filled in after `python scripts/run_eval_2026_05_30b.py`.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

API = "https://novum-prod.duckdns.org"

# IP-37 (postov) baseline for behavioral floor check
POSTOV = [
    ("Q1", "a2500f9d-ecc3-450f-9ff1-c594074c529a", 17.0),
    ("Q2", "d7c478c2-555e-4adf-a201-0a98814bc5c2", 33.0),
    ("Q3", "141e8b79-e6a9-41cf-b360-462ad78f9a14", 39.0),
    ("Q4", "9705a37c-6cb7-40eb-8550-add44a200fec", 98.0),
    ("Q5", "c00de3bb-0345-4f51-ab0d-f3beb9ff43e7", 100.0),
    ("Q6", "2d026f6f-5cf0-4fd7-a473-8c6d046cf3a5", 88.0),
    ("Q7", "36c42cd4-55df-4638-99ad-fa669d219f4a", 280.0),
    ("Q8", "640013a3-bdb7-4629-b03f-723295c15228", 88.0),
]

# IP-38 (postinst) — instrumentation only. Filled by main() from eval_postinst.txt.
POSTINST: list[tuple] = []


def fetch_events(run_id: str) -> list[dict]:
    url = f"{API}/api/runs/{run_id}/events"
    req = urllib.request.Request(url, headers={"Accept": "text/event-stream"})
    events: list[dict] = []
    with urllib.request.urlopen(req, timeout=180) as resp:
        event_name = None
        data_buf: list[str] = []
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").rstrip("\n").rstrip("\r")
            if line == "":
                if event_name and data_buf:
                    payload_raw = "\n".join(data_buf)
                    try:
                        payload = json.loads(payload_raw)
                    except json.JSONDecodeError:
                        payload = {"_raw": payload_raw}
                    events.append({"event": event_name, "data": payload})
                    if event_name == "Stopped":
                        break
                event_name = None
                data_buf = []
                continue
            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                event_name = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_buf.append(line[len("data:"):].lstrip())
    return events


def summarize(label: str, run_id: str, wallclock: float | None, events: list[dict]) -> dict:
    route = stop_reason = answer_kind = None
    judge_score = structural_score = final_confidence = None
    coverage = agreement = None  # may come from JudgeRuled (IP-38) or ConfidenceCalculated
    override_eligible: bool | None = None
    override_blockers: list[str] | None = None
    judge_passed: bool | None = None
    contradictions: list | None = None
    cost_usd = 0.0
    src_counter: Counter[str] = Counter()
    host_counter: Counter[str] = Counter()
    prose_excerpt = None
    claim_count = 0
    for e in events:
        name = e["event"]
        d = e["data"] if isinstance(e["data"], dict) else {}
        if name == "RouteSelected":
            route = d.get("route") or d.get("lane") or route
        elif name == "PlanCreated":
            sc = d.get("sub_claims") or []
            if isinstance(sc, list):
                claim_count = len(sc)
        elif name == "JudgeRuled":
            judge_score = d.get("judge_score", d.get("judge_confidence", judge_score))
            structural_score = d.get("structural_confidence", structural_score)
            judge_passed = d.get("passed", judge_passed)
            contradictions = d.get("contradictions_detected", contradictions)
            # IP-38 extras (via extra="allow")
            if d.get("coverage") is not None:
                coverage = d.get("coverage")
            if d.get("agreement") is not None:
                agreement = d.get("agreement")
            if "override_eligible" in d:
                override_eligible = d.get("override_eligible")
            if "override_blockers" in d:
                override_blockers = d.get("override_blockers")
        elif name == "ConfidenceCalculated":
            final_confidence = d.get("final_confidence", final_confidence)
            if coverage is None:
                coverage = d.get("coverage", coverage)
            if agreement is None:
                agreement = d.get("agreement", agreement)
        elif name == "Stopped":
            stop_reason = d.get("stop_reason") or stop_reason
            answer_kind = d.get("answer_kind") or d.get("selected_answer_kind") or answer_kind
            final_confidence = d.get("final_confidence", final_confidence)
        elif name == "EvidenceAdded":
            src_counter[str(d.get("source_type") or "?")] += 1
            url = d.get("source_url") or ""
            try:
                host = urllib.parse.urlparse(url).hostname or ""
                if host.startswith("www."):
                    host = host[4:]
            except Exception:
                host = ""
            if host:
                host_counter[host] += 1
        elif name == "DraftSynthesized":
            if not prose_excerpt:
                prose = (d.get("answer") or d.get("prose") or "")
                prose_excerpt = prose[:400]
        elif name == "CostIncurred":
            cost_usd += float(d.get("cost_usd", 0.0) or 0.0)

    bl_strict_ok = False
    bl_word_count = 0
    if prose_excerpt:
        first = re.split(r"(?<=[.!?])\s+", prose_excerpt.strip(), maxsplit=1)[0]
        bl_word_count = len(first.split())
        bl_strict_ok = 4 <= bl_word_count <= 25

    return {
        "label": label,
        "run_id": run_id[:8],
        "wallclock_s": wallclock,
        "route": route,
        "stop_reason": stop_reason,
        "answer_kind": answer_kind,
        "S": structural_score,
        "J": judge_score,
        "judge_passed": judge_passed,
        "contradictions_count": len(contradictions) if contradictions else 0,
        "conf": final_confidence,
        "coverage": coverage,
        "agreement": agreement,
        "override_eligible": override_eligible,
        "override_blockers": override_blockers,
        "claim_count": claim_count,
        "evidence_total": sum(src_counter.values()),
        "host_counter": dict(host_counter),
        "unique_hosts": len(host_counter),
        "cost_usd": cost_usd,
        "prose_excerpt": prose_excerpt,
        "bl_strict_ok": bl_strict_ok,
        "bl_word_count": bl_word_count,
    }


def parse_eval_log(path: Path) -> list[tuple]:
    """Parse eval_postinst.txt for (label, run_id, wallclock) tuples in Q order."""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    # Look for `run_id=<uuid>` and `stopped after Ns :: stop_reason=...`
    rid_re = re.compile(r"run_id=([0-9a-f-]{36})")
    wall_re = re.compile(r"stopped after (\d+)s")
    rids = rid_re.findall(text)
    walls = [float(x) for x in wall_re.findall(text)]
    labels = [f"Q{i+1}" for i in range(len(rids))]
    out: list[tuple] = []
    for i, rid in enumerate(rids[:8]):
        wc = walls[i] if i < len(walls) else None
        out.append((labels[i], rid, wc))
    return out


def fetch_set(name: str, items: list[tuple]) -> list[dict]:
    rows: list[dict] = []
    print(f"[fetch] {name}...")
    for tup in items:
        label, rid = tup[0], tup[1]
        wc = tup[2] if len(tup) > 2 else None
        print(f"  [{label}] {rid[:8]} ...", flush=True)
        try:
            evs = fetch_events(rid)
            rows.append(summarize(label, rid, wc, evs))
        except Exception as exc:
            print(f"    ERROR: {exc}", flush=True)
            rows.append({"label": label, "run_id": rid[:8], "error": str(exc)})
    return rows


def main() -> int:
    global POSTINST
    POSTINST = parse_eval_log(Path("eval_postinst.txt"))
    if not POSTINST:
        print("ERROR: eval_postinst.txt not found or empty. Run scripts/run_eval_2026_05_30b.py first.", file=sys.stderr)
        return 1
    print(f"[parsed] {len(POSTINST)} run_ids from eval_postinst.txt")

    inst = fetch_set("postinst (IP-38 instrumented)", POSTINST)
    ov = fetch_set("postov (IP-37 baseline)", POSTOV)

    # ====================================================================
    # P1 — Primary metric: telemetry completeness
    # ====================================================================
    print("\n=== IP-38 PRIMARY METRIC — telemetry completeness ===")
    telemetry_complete = 0
    for r in inst:
        if "error" in r:
            continue
        # Q1 is FAST lane — synthetic JudgeRuled may not carry overrides.
        # Q3 had S=0.15 (zero evidence) — judge may emit but override fields optional.
        # The contract is: STANDARD/DEEP runs that go through _handle_judging
        # MUST expose coverage+agreement+override_eligible+override_blockers.
        # Empty list ([]) for blockers counts as "exposed".
        exposed = (
            r["coverage"] is not None
            and r["agreement"] is not None
            and r["override_eligible"] is not None
            and r["override_blockers"] is not None
        )
        marker = "OK " if exposed else "XX "
        print(
            f"  {r['label']:3} {marker} route={str(r['route'] or '-'):9} "
            f"cov={r['coverage']} agr={r['agreement']} "
            f"override_eligible={r['override_eligible']} blockers={r['override_blockers']}"
        )
        if exposed:
            telemetry_complete += 1
    n_inst = sum(1 for r in inst if "error" not in r)
    print(f"\n  telemetry_complete = {telemetry_complete}/{n_inst}  (target: {n_inst}/{n_inst} or close)")

    # ====================================================================
    # P1 — Secondary metric: stop_reason floor (no regression vs postov)
    # ====================================================================
    def stop_count(rows): return Counter(r.get("stop_reason") for r in rows if "error" not in r)
    print("\n=== STOP REASON FLOOR CHECK (postov baseline) ===")
    a, b = stop_count(ov), stop_count(inst)
    keys = sorted(set(a) | set(b))
    print(f"  {'reason':25} {'postov':>8} {'postinst':>10}")
    for k in keys:
        print(f"  {k:25} {a.get(k, 0):>8} {b.get(k, 0):>10}")
    jc_postov = a.get("judge_confirmed", 0)
    jc_postinst = b.get("judge_confirmed", 0)
    jc_floor_ok = jc_postinst >= jc_postov
    print(f"\n  judge_confirmed floor: postov={jc_postov} postinst={jc_postinst}  {'PASS' if jc_floor_ok else 'FAIL'}")

    # ====================================================================
    # P1 — Secondary metric: BL strict floor (no regression vs postov)
    # ====================================================================
    bl_ov = sum(1 for r in ov if not r.get("error") and r.get("bl_strict_ok"))
    bl_inst = sum(1 for r in inst if not r.get("error") and r.get("bl_strict_ok"))
    bl_floor_ok = bl_inst >= bl_ov
    print(f"  BL strict floor: postov={bl_ov}/8 postinst={bl_inst}/8  {'PASS' if bl_floor_ok else 'FAIL'}")

    # ====================================================================
    # IP-38 DIAGNOSTIC ROLLUP — which gate blocks each non-confirmed run?
    # ====================================================================
    print("\n=== IP-39 PREP — what blocks each non-confirmed run? ===")
    blocker_tally: Counter[str] = Counter()
    for r in inst:
        if "error" in r:
            continue
        if r.get("stop_reason") != "judge_confirmed" and r.get("override_blockers"):
            for b in r["override_blockers"]:
                blocker_tally[b] += 1
            print(
                f"  {r['label']:3} S={r['S']} cov={r['coverage']} agr={r['agreement']} "
                f"blockers={r['override_blockers']}"
            )
    print(f"\n  blocker frequency: {dict(blocker_tally)}")
    print("  -> use this to pick the IP-39 threshold to relax (e.g. 'coverage' dominates -> bump 0.6 -> 0.5)")

    # ====================================================================
    # PER-QUESTION TABLE
    # ====================================================================
    print("\n=== PER QUESTION (postinst, IP-38) ===")
    for r in inst:
        if "error" in r:
            print(f"  {r['label']:3} ERROR {r['error']}")
            continue
        cov = '-' if r['coverage'] is None else f"{r['coverage']:.2f}"
        agr = '-' if r['agreement'] is None else f"{r['agreement']:.2f}"
        s = '-' if r['S'] is None else f"{r['S']:.2f}"
        ovr = '?' if r['override_eligible'] is None else ('y' if r['override_eligible'] else '.')
        print(
            f"  {r['label']:3} {str(r['route'] or '-'):9} "
            f"{str(r['stop_reason'] or '-')[:22]:22} "
            f"S={s:>5} cov={cov:>5} agr={agr:>5} override={ovr} "
            f"ev={r['evidence_total']:>3} h={r['unique_hosts']:>2} "
            f"BL25={'y' if r['bl_strict_ok'] else '.'}({r['bl_word_count']:>2}w) "
            f"t={(r['wallclock_s'] or 0):.0f}s"
        )

    # ====================================================================
    # VERDICT (per IP-38 hypothesis falsification rule)
    # ====================================================================
    print("\n=== IP-38 VERDICT ===")
    telemetry_ok = telemetry_complete >= (n_inst - 2)  # tolerate FAST+zero-evidence edge cases
    verdict = "PASS" if (telemetry_ok and jc_floor_ok and bl_floor_ok) else "FAIL"
    print(f"  telemetry_complete {telemetry_complete}/{n_inst} {'PASS' if telemetry_ok else 'FAIL'}")
    print(f"  judge_confirmed   floor  {'PASS' if jc_floor_ok else 'FAIL'}")
    print(f"  BL_strict         floor  {'PASS' if bl_floor_ok else 'FAIL'}")
    print(f"  >>> VERDICT: {verdict}")

    Path("compare_postinst.json").write_text(
        json.dumps({"postinst": inst, "postov": ov, "blocker_tally": dict(blocker_tally), "verdict": verdict}, indent=2),
        encoding="utf-8",
    )
    print("\n[done] wrote compare_postinst.json")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
