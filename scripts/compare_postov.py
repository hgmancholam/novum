"""Compare IP-37 (postov, structural override) vs IP-36 (postj) vs IP-33+34+35 (postq).

Clone of compare_postj.py with POSTOV as the new iteration.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from collections import Counter

API = "https://novum-prod.duckdns.org"

# IP-37 (postov)
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

# IP-36 (postj)
POSTJ = [
    ("Q1", "d344e581-5b01-4324-a70b-b8a3d73198b5"),
    ("Q2", "a51231ec-0768-400a-ab1c-76bc6efe7c43"),
    ("Q3", "4433b3e9-619c-4e1d-b8d5-62a9d3c4ae05"),
    ("Q4", "24c11419-5e70-4810-a5c9-4d95e8521a35"),
    ("Q5", "3c16e18e-0104-47ba-8a8c-cc8fc18f3b2f"),
    ("Q6", "7dd1bdd7-9932-4b29-af3b-8e80880783d4"),
    ("Q7", "b784ef85-9cd2-4a01-b406-e0409ef6e281"),
    ("Q8", "f32fae3e-5b44-47d7-a821-bf98a1762653"),
]

# IP-33+34+35 (postq)
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
    coverage = agreement = None
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
            coverage = d.get("coverage", coverage)
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
        "coverage": coverage,
        "agreement": agreement,
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
    ov = fetch_set("postov (IP-37)", POSTOV)
    j = fetch_set("postj (IP-36)", POSTJ)
    q = fetch_set("postq (IP-33+34+35)", POSTQ)

    def stop_count(rows): return Counter(r["stop_reason"] for r in rows if "error" not in r)
    print("\n=== STOP REASON (postq -> postj -> postov) ===")
    a, b, c = stop_count(q), stop_count(j), stop_count(ov)
    keys = sorted(set(a) | set(b) | set(c))
    print(f"  {'reason':25} {'postq':>8} {'postj':>8} {'postov':>8}")
    for k in keys:
        print(f"  {k:25} {a.get(k, 0):>8} {b.get(k, 0):>8} {c.get(k, 0):>8}")

    print("\n=== PER QUESTION (postov, IP-37) ===")
    for r in ov:
        if "error" in r:
            print(f"  {r['label']:3} ERROR {r['error']}")
            continue
        cov = '-' if r['coverage'] is None else f"{r['coverage']:.2f}"
        agr = '-' if r['agreement'] is None else f"{r['agreement']:.2f}"
        print(
            f"  {r['label']:3} {str(r['route'] or '-'):9} "
            f"{str(r['stop_reason'] or '-')[:22]:22} "
            f"kind={str(r['answer_kind'] or '-')[:13]:13} "
            f"claims={r['claim_count']:>2} "
            f"S={('-' if r['S'] is None else f'{r['S']:.2f}'):>5} "
            f"cov={cov:>5} agr={agr:>5} "
            f"ev={r['evidence_total']:>3} h={r['unique_hosts']:>2} "
            f"BL25={'y' if r['bl_strict_ok'] else '.'}({r['bl_word_count']:>2}w) "
            f"t={(r['wallclock_s'] or 0):.0f}s"
        )

    print("\n=== STOP DELTA (postj -> postov) ===")
    by_j = {r["label"]: r for r in j if "error" not in r}
    for r in ov:
        if "error" in r:
            continue
        prev = by_j.get(r["label"], {}).get("stop_reason") or "-"
        cur = r.get("stop_reason") or "-"
        delta = "  <- flipped" if prev != cur else ""
        print(f"  {r['label']:3} {str(prev):20} -> {str(cur):20}{delta}")

    print("\n=== BOTTOM LINE STRICT CHECK (<=25 words) — postov ===")
    for r in ov:
        if "error" in r:
            continue
        first = ""
        if r["prose_excerpt"]:
            first = re.split(r"(?<=[.!?])\s+", r["prose_excerpt"].strip(), maxsplit=1)[0]
        print(f"  {r['label']:3} BL25_ok={r['bl_strict_ok']} ({r['bl_word_count']}w) :: {first[:180]}")

    print("\n=== SOURCES PER QUESTION (postov) ===")
    for r in ov:
        if "error" in r:
            continue
        hosts = sorted(r["host_counter"].items(), key=lambda kv: -kv[1])
        host_str = ", ".join(f"{h}x{c}" for h, c in hosts[:10])
        print(f"  {r['label']:3} ({r['unique_hosts']} hosts): {host_str}")

    def bl_pass(rows):
        ok = sum(1 for r in rows if "error" not in r and r.get("bl_strict_ok"))
        n = sum(1 for r in rows if "error" not in r)
        return ok, n

    def jc_rate(rows):
        ok = sum(1 for r in rows if "error" not in r and r.get("stop_reason") == "judge_confirmed")
        n = sum(1 for r in rows if "error" not in r)
        return ok, n

    q_bl = bl_pass(q); j_bl = bl_pass(j); ov_bl = bl_pass(ov)
    q_jc = jc_rate(q); j_jc = jc_rate(j); ov_jc = jc_rate(ov)
    print(f"\n=== BL strict (<=25w) PASS RATE ===  postq={q_bl[0]}/{q_bl[1]}  postj={j_bl[0]}/{j_bl[1]}  postov={ov_bl[0]}/{ov_bl[1]}")
    print(f"=== judge_confirmed RATE ===  postq={q_jc[0]}/{q_jc[1]}  postj={j_jc[0]}/{j_jc[1]}  postov={ov_jc[0]}/{ov_jc[1]}")

    out = {"postov": ov, "postj": j, "postq": q}
    with open("compare_postov.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print("\n[done] wrote compare_postov.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
