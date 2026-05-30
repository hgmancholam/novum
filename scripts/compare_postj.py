"""Compare IP-36 (postj) vs IP-33+34+35 (postq) vs IP-32 (postux).

Clone of compare_postq.py with POSTJ as the new run and POSTQ as the previous
baseline. IP-36 = planner caps STANDARD claims to 1-3 + judge prompt relaxes
the "completeness" rule. Goal: lift judge_confirmed share without losing the
BL strict ≤25w gains from postq.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from collections import Counter

API = "https://novum-prod.duckdns.org"

# IP-36 (postj) — latest
POSTJ = [
    ("Q1", "d344e581-5b01-4324-a70b-b8a3d73198b5", 17.0),
    ("Q2", "a51231ec-0768-400a-ab1c-76bc6efe7c43", 67.0),
    ("Q3", "4433b3e9-619c-4e1d-b8d5-62a9d3c4ae05", 39.0),
    ("Q4", "24c11419-5e70-4810-a5c9-4d95e8521a35", 327.0),
    ("Q5", "3c16e18e-0104-47ba-8a8c-cc8fc18f3b2f", 106.0),
    ("Q6", "7dd1bdd7-9932-4b29-af3b-8e80880783d4", 67.0),
    ("Q7", "b784ef85-9cd2-4a01-b406-e0409ef6e281", 113.0),
    ("Q8", "f32fae3e-5b44-47d7-a821-bf98a1762653", 89.0),
]

# IP-33+34+35 (postq) — previous baseline
POSTQ = [
    ("Q1", "ccfd325a-478e-42d9-a457-1c3a4037e0c0"),
    ("Q2", "4a95338e-11cf-4789-b21c-a14e6ecbb2cd"),
    ("Q3", "0133d42a-b13c-4488-83bb-ecf830ae7ae9"),
    ("Q4", "2a43e90a-a439-479e-b3c2-6ab0552db789"),
    ("Q5", "8d7bae73-5a90-412d-8863-c3e7750c7103"),
    ("Q6", "7f4debec-39de-48b4-af6b-61c9b97886f0"),
    ("Q7", "96a7ac7d-f261-4960-a21a-92f07f7e1da6"),
    ("Q8", "cf9cb27d-d2a6-4635-b797-68daeea486fd"),
]

# IP-32 (postux)
POSTUX = [
    ("Q1", "6692c8b4-a08c-4dbb-a072-96b9e96abda9"),
    ("Q2", "55b06fa0-3ef2-4180-a9da-ef03bc2a55ce"),
    ("Q3", "1f2a72bb-95f9-48f3-97ca-9f5f5814131d"),
    ("Q4", "481b7f30-4b7f-48fe-8d0e-c01220bd794a"),
    ("Q5", "69d579cd-4721-4097-a6a3-ede2052d0748"),
    ("Q6", "ae77df76-25a0-4db9-be50-0ac543a88b34"),
    ("Q7", "3e2643e1-3568-4674-9479-f40326b53cbf"),
    ("Q8", "5c45a43d-26d7-4df0-9c9c-6dd97a1accdd"),
]


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
    route = stop_reason = answer_kind = domain = None
    judge_score = structural_score = final_confidence = None
    cost_usd = 0.0
    src_counter: Counter[str] = Counter()
    host_counter: Counter[str] = Counter()
    tier_counter: Counter[str] = Counter()
    prose_excerpt = None
    claim_count = 0
    for e in events:
        name = e["event"]
        d = e["data"] if isinstance(e["data"], dict) else {}
        if name == "RouteSelected":
            route = d.get("route") or d.get("lane") or route
        elif name == "QuestionClassified":
            domain = d.get("domain") or domain
        elif name == "PlanCreated":
            sc = d.get("sub_claims") or []
            if isinstance(sc, list):
                claim_count = len(sc)
        elif name == "JudgeRuled":
            judge_score = d.get("judge_score", judge_score)
            structural_score = d.get("structural_confidence", structural_score)
        elif name == "ConfidenceCalculated":
            final_confidence = d.get("final_confidence", final_confidence)
            structural_score = d.get("structural_confidence", structural_score)
            judge_score = d.get("judge_score", judge_score)
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
            tier = d.get("authority_tier") or "unknown"
            tier_counter[str(tier)] += 1
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
        "domain": domain,
        "stop_reason": stop_reason,
        "answer_kind": answer_kind,
        "S": structural_score,
        "J": judge_score,
        "conf": final_confidence,
        "claim_count": claim_count,
        "evidence_total": sum(src_counter.values()),
        "host_counter": dict(host_counter),
        "unique_hosts": len(host_counter),
        "tier_counter": dict(tier_counter),
        "cost_usd": cost_usd,
        "prose_excerpt": prose_excerpt,
        "bl_strict_ok": bl_strict_ok,
        "bl_word_count": bl_word_count,
    }


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
    j = fetch_set("postj (IP-36)", POSTJ)
    q = fetch_set("postq (IP-33+34+35)", POSTQ)
    ux = fetch_set("postux (IP-32)", POSTUX)

    def stop_count(rows): return Counter(r["stop_reason"] for r in rows if "error" not in r)
    print("\n=== STOP REASON (postux -> postq -> postj) ===")
    a, b, c = stop_count(ux), stop_count(q), stop_count(j)
    keys = sorted(set(a) | set(b) | set(c))
    print(f"  {'reason':25} {'postux':>10} {'postq':>8} {'postj':>8}")
    for k in keys:
        print(f"  {k:25} {a.get(k, 0):>10} {b.get(k, 0):>8} {c.get(k, 0):>8}")

    print("\n=== PER QUESTION (postj, IP-36) ===")
    for r in j:
        if "error" in r:
            print(f"  {r['label']:3} ERROR {r['error']}")
            continue
        print(
            f"  {r['label']:3} {str(r['route'] or '-'):9} dom={str(r['domain'] or '-'):20} "
            f"{str(r['stop_reason'] or '-')[:22]:22} "
            f"kind={str(r['answer_kind'] or '-')[:13]:13} "
            f"claims={r['claim_count']:>2} "
            f"S={('-' if r['S'] is None else f'{r['S']:.2f}'):>5} "
            f"J={('-' if r['J'] is None else f'{r['J']:.2f}'):>5} "
            f"ev={r['evidence_total']:>3} hosts={r['unique_hosts']:>2} "
            f"BL25={'y' if r['bl_strict_ok'] else '.'}({r['bl_word_count']:>2}w) "
            f"$={r['cost_usd']:.4f} t={(r['wallclock_s'] or 0):.0f}s"
        )

    print("\n=== PER QUESTION (postq, prev baseline) ===")
    for r in q:
        if "error" in r:
            continue
        print(
            f"  {r['label']:3} {str(r['route'] or '-'):9} "
            f"{str(r['stop_reason'] or '-')[:22]:22} "
            f"kind={str(r['answer_kind'] or '-')[:13]:13} "
            f"claims={r['claim_count']:>2} "
            f"S={('-' if r['S'] is None else f'{r['S']:.2f}'):>5} "
            f"J={('-' if r['J'] is None else f'{r['J']:.2f}'):>5} "
            f"ev={r['evidence_total']:>3} hosts={r['unique_hosts']:>2} "
            f"BL25={'y' if r['bl_strict_ok'] else '.'}({r['bl_word_count']:>2}w)"
        )

    print("\n=== ANSWER KIND COMPARISON (postq -> postj) ===")
    by_q = {r["label"]: r for r in q if "error" not in r}
    print(f"  {'Q':3} {'postq kind':15} {'postj kind':15}  delta")
    for r in j:
        if "error" in r:
            continue
        prev = by_q.get(r["label"], {}).get("answer_kind") or "-"
        cur = r.get("answer_kind") or "-"
        delta = "" if prev == cur else "  <- changed"
        print(f"  {r['label']:3} {str(prev):15} {str(cur):15}{delta}")

    print("\n=== AUTHORITY TIER BREAKDOWN (postj) ===")
    print(f"  {'Q':3} {'primary':>8} {'reputable':>10} {'general':>8} {'low':>5} {'total':>6}")
    for r in j:
        if "error" in r:
            continue
        t = r["tier_counter"]
        prim = t.get("PRIMARY_AUTHORITATIVE", 0)
        rep = t.get("REPUTABLE_SECONDARY", 0)
        gen = t.get("GENERAL", 0)
        low = t.get("LOW_SIGNAL", 0)
        total = prim + rep + gen + low
        print(f"  {r['label']:3} {prim:>8} {rep:>10} {gen:>8} {low:>5} {total:>6}")

    print("\n=== SOURCES PER QUESTION (postj) ===")
    for r in j:
        if "error" in r:
            continue
        hosts = sorted(r["host_counter"].items(), key=lambda kv: -kv[1])
        host_str = ", ".join(f"{h}x{c}" for h, c in hosts[:10])
        print(f"  {r['label']:3} ({r['unique_hosts']} hosts): {host_str}")

    print("\n=== BOTTOM LINE STRICT CHECK (<=25 words) — postj ===")
    for r in j:
        if "error" in r:
            continue
        first = ""
        if r["prose_excerpt"]:
            first = re.split(r"(?<=[.!?])\s+", r["prose_excerpt"].strip(), maxsplit=1)[0]
        print(f"  {r['label']:3} BL25_ok={r['bl_strict_ok']} ({r['bl_word_count']}w) :: {first[:180]}")

    print("\n=== BOTTOM LINE EXCERPTS (postq, prev baseline) ===")
    for r in q:
        if "error" in r:
            continue
        first = ""
        if r["prose_excerpt"]:
            first = re.split(r"(?<=[.!?])\s+", r["prose_excerpt"].strip(), maxsplit=1)[0]
        wc = len(first.split())
        print(f"  {r['label']:3} ({wc}w) :: {first[:180]}")

    def authority_share(rows):
        cc = Counter()
        for r in rows:
            if "error" in r:
                continue
            for k, v in r["tier_counter"].items():
                cc[k] += v
        total = sum(cc.values()) or 1
        return ({k: round(cc[k] / total, 3) for k in
                 ["PRIMARY_AUTHORITATIVE", "REPUTABLE_SECONDARY", "GENERAL", "LOW_SIGNAL"]},
                sum(cc.values()))

    u_share, u_tot = authority_share(ux)
    q_share, q_tot = authority_share(q)
    j_share, j_tot = authority_share(j)
    print("\n=== AUTHORITY SHARE (fraction of evidence) ===")
    print(f"  {'tier':25} {'postux':>10} {'postq':>8} {'postj':>8}")
    for t in ["PRIMARY_AUTHORITATIVE", "REPUTABLE_SECONDARY", "GENERAL", "LOW_SIGNAL"]:
        print(f"  {t:25} {u_share[t]:>10.3f} {q_share[t]:>8.3f} {j_share[t]:>8.3f}")
    print(f"  {'total evidence':25} {u_tot:>10} {q_tot:>8} {j_tot:>8}")

    def bl_pass(rows):
        ok = sum(1 for r in rows if "error" not in r and r.get("bl_strict_ok"))
        n = sum(1 for r in rows if "error" not in r)
        return ok, n

    u_ok, u_n = bl_pass(ux)
    q_ok, q_n = bl_pass(q)
    j_ok, j_n = bl_pass(j)
    print(f"\n=== BL strict (<=25w) PASS RATE ===  postux={u_ok}/{u_n}  postq={q_ok}/{q_n}  postj={j_ok}/{j_n}")

    def jc_rate(rows):
        ok = sum(1 for r in rows if "error" not in r and r.get("stop_reason") == "judge_confirmed")
        n = sum(1 for r in rows if "error" not in r)
        return ok, n

    u_jc = jc_rate(ux); q_jc = jc_rate(q); j_jc = jc_rate(j)
    print(f"=== judge_confirmed RATE ===  postux={u_jc[0]}/{u_jc[1]}  postq={q_jc[0]}/{q_jc[1]}  postj={j_jc[0]}/{j_jc[1]}")

    out = {"postj": j, "postq": q, "postux": ux,
           "authority_share": {"postux": u_share, "postq": q_share, "postj": j_share}}
    with open("compare_postj.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print("\n[done] wrote compare_postj.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
