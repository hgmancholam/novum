"""Compare IP-32 (postux, 2026-05-30) vs IP-31 (postdomain) vs postA1A2.

Adds authority-tier breakdown, prose excerpt with Bottom Line check, and
host bucket fractions (LOW_SIGNAL hosts vs total).
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from collections import Counter

API = "https://novum-prod.duckdns.org"

# IP-32 (postux) - latest
POSTUX = [
    ("Q1", "6692c8b4-a08c-4dbb-a072-96b9e96abda9", 17.0),
    ("Q2", "55b06fa0-3ef2-4180-a9da-ef03bc2a55ce", 84.0),
    ("Q3", "1f2a72bb-95f9-48f3-97ca-9f5f5814131d", 39.6),
    ("Q4", "481b7f30-4b7f-48fe-8d0e-c01220bd794a", 95.3),
    ("Q5", "69d579cd-4721-4097-a6a3-ede2052d0748", 83.2),
    ("Q6", "ae77df76-25a0-4db9-be50-0ac543a88b34", 110.8),
    ("Q7", "3e2643e1-3568-4674-9479-f40326b53cbf", 112.0),
    ("Q8", "5c45a43d-26d7-4df0-9c9c-6dd97a1accdd", 117.8),
]

# IP-31 (postdomain)
POSTDOMAIN = [
    ("Q1", "2e55036d-18d6-421f-93ed-7efce26c5216"),
    ("Q2", "46736c54-8252-40ec-b0ed-6cd4da85bcf5"),
    ("Q3", "f1ddb63d-954b-478f-932a-a91724b3fb1a"),
    ("Q4", "6d379ce5-62ff-40df-8fce-45a840625279"),
    ("Q5", "87afe243-171f-45ae-8cea-9b8271e9f5ea"),
    ("Q6", "f906ab84-bb7c-4cdb-b9af-3e48afdfe52b"),
    ("Q7", "3feaf0b7-a9f2-4736-9e5b-aea8ebda4eb0"),
    ("Q8", "a2243165-9c20-463a-b8ed-e805c635ddb9"),
]

# postA1A2 (pre-IP-31)
POSTA1A2 = [
    ("Q1", "79737678-270a-426b-9981-807bc7098386"),
    ("Q2", "ccbd12cc-5570-4e26-99ec-e1fe64a3910a"),
    ("Q3", "ae3a8648-079d-441c-bab3-372b54d6f997"),
    ("Q4", "9c713a41-6920-4dc3-a463-b844c0f1ab56"),
    ("Q5", "85130b57-1cb1-4b0f-a761-807066660a91"),
    ("Q6", "749ceb67-81dd-4c40-b9c8-43a78f81e530"),
    ("Q7", "c5b1ea1c-39e2-4128-9d61-d477b877f252"),
    ("Q8", "d9b53537-0944-42ca-aeee-15d8e5585553"),
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
    for e in events:
        name = e["event"]
        d = e["data"] if isinstance(e["data"], dict) else {}
        if name == "RouteSelected":
            route = d.get("route") or d.get("lane") or route
        elif name == "QuestionClassified":
            domain = d.get("domain") or domain
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

    # bottom-line check: first sentence of prose <= 30 words + ends with .?!
    bottom_line_ok = False
    if prose_excerpt:
        first = re.split(r"(?<=[.!?])\s+", prose_excerpt.strip(), maxsplit=1)[0]
        wc = len(first.split())
        bottom_line_ok = 4 <= wc <= 30

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
        "evidence_total": sum(src_counter.values()),
        "host_counter": dict(host_counter),
        "unique_hosts": len(host_counter),
        "tier_counter": dict(tier_counter),
        "cost_usd": cost_usd,
        "prose_excerpt": prose_excerpt,
        "bottom_line_ok": bottom_line_ok,
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
    ux = fetch_set("postux (IP-32)", POSTUX)
    dom = fetch_set("postdomain (IP-31)", POSTDOMAIN)
    a1a2 = fetch_set("postA1A2", POSTA1A2)

    def stop_count(rows): return Counter(r["stop_reason"] for r in rows if "error" not in r)
    a1a2_c = stop_count(a1a2)
    dom_c = stop_count(dom)
    ux_c = stop_count(ux)

    print("\n=== STOP REASON (postA1A2 -> postdomain -> postux) ===")
    keys = sorted(set(a1a2_c) | set(dom_c) | set(ux_c))
    print(f"  {'reason':25} {'postA1A2':>10} {'postdomain':>12} {'postux':>10}")
    for k in keys:
        print(f"  {k:25} {a1a2_c.get(k, 0):>10} {dom_c.get(k, 0):>12} {ux_c.get(k, 0):>10}")

    print("\n=== PER QUESTION (postux, IP-32) ===")
    for r in ux:
        if "error" in r:
            print(f"  {r['label']:3} ERROR {r['error']}")
            continue
        print(
            f"  {r['label']:3} {str(r['route'] or '-'):9} dom={str(r['domain'] or '-'):20} "
            f"{str(r['stop_reason'] or '-')[:22]:22} "
            f"S={('-' if r['S'] is None else f'{r['S']:.2f}'):>5} "
            f"J={('-' if r['J'] is None else f'{r['J']:.2f}'):>5} "
            f"conf={('-' if r['conf'] is None else f'{r['conf']:.2f}'):>5} "
            f"ev={r['evidence_total']:>3} hosts={r['unique_hosts']:>2} "
            f"BL={'y' if r['bottom_line_ok'] else '.'} "
            f"$={r['cost_usd']:.4f} t={(r['wallclock_s'] or 0):.0f}s"
        )

    print("\n=== AUTHORITY TIER BREAKDOWN (postux) ===")
    print(f"  {'Q':3} {'primary':>8} {'reputable':>10} {'general':>8} {'low':>5} {'total':>6}")
    for r in ux:
        if "error" in r:
            continue
        t = r["tier_counter"]
        prim = t.get("PRIMARY_AUTHORITATIVE", 0)
        rep = t.get("REPUTABLE_SECONDARY", 0)
        gen = t.get("GENERAL", 0)
        low = t.get("LOW_SIGNAL", 0)
        total = prim + rep + gen + low
        print(f"  {r['label']:3} {prim:>8} {rep:>10} {gen:>8} {low:>5} {total:>6}")

    print("\n=== AUTHORITY TIER BREAKDOWN (postdomain, for comparison) ===")
    print(f"  {'Q':3} {'primary':>8} {'reputable':>10} {'general':>8} {'low':>5} {'total':>6}")
    for r in dom:
        if "error" in r:
            continue
        t = r["tier_counter"]
        prim = t.get("PRIMARY_AUTHORITATIVE", 0)
        rep = t.get("REPUTABLE_SECONDARY", 0)
        gen = t.get("GENERAL", 0)
        low = t.get("LOW_SIGNAL", 0)
        total = prim + rep + gen + low
        print(f"  {r['label']:3} {prim:>8} {rep:>10} {gen:>8} {low:>5} {total:>6}")

    print("\n=== SOURCES PER QUESTION (postux) ===")
    for r in ux:
        if "error" in r:
            continue
        hosts = sorted(r["host_counter"].items(), key=lambda kv: -kv[1])
        host_str = ", ".join(f"{h}x{c}" for h, c in hosts[:10])
        print(f"  {r['label']:3} ({r['unique_hosts']} hosts): {host_str}")

    print("\n=== SOURCES PER QUESTION (postdomain) ===")
    for r in dom:
        if "error" in r:
            continue
        hosts = sorted(r["host_counter"].items(), key=lambda kv: -kv[1])
        host_str = ", ".join(f"{h}x{c}" for h, c in hosts[:10])
        print(f"  {r['label']:3} ({r['unique_hosts']} hosts): {host_str}")

    print("\n=== CONFIDENCE PER QUESTION (postA1A2 -> postdomain -> postux) ===")
    by_a = {r["label"]: r for r in a1a2 if "error" not in r}
    by_d = {r["label"]: r for r in dom if "error" not in r}
    print(f"  {'Q':3} {'a1a2C':>7} {'domC':>7} {'uxC':>7} {'a1a2H':>6} {'domH':>6} {'uxH':>6}")
    for r in ux:
        if "error" in r:
            continue
        a = by_a.get(r["label"], {})
        d = by_d.get(r["label"], {})
        def fmt(x): return "-" if x is None else f"{x:.2f}"
        print(
            f"  {r['label']:3} {fmt(a.get('conf')):>7} {fmt(d.get('conf')):>7} {fmt(r['conf']):>7} "
            f"{a.get('unique_hosts', 0):>6} {d.get('unique_hosts', 0):>6} {r['unique_hosts']:>6}"
        )

    print("\n=== BOTTOM LINE PROSE EXCERPTS (postux) ===")
    for r in ux:
        if "error" in r:
            continue
        first = ""
        if r["prose_excerpt"]:
            first = re.split(r"(?<=[.!?])\s+", r["prose_excerpt"].strip(), maxsplit=1)[0]
        print(f"  {r['label']:3} BL_ok={r['bottom_line_ok']} :: {first[:160]}")

    # Aggregate authority share
    def authority_share(rows):
        c = Counter()
        for r in rows:
            if "error" in r:
                continue
            for k, v in r["tier_counter"].items():
                c[k] += v
        total = sum(c.values()) or 1
        return {k: round(c[k] / total, 3) for k in ["PRIMARY_AUTHORITATIVE", "REPUTABLE_SECONDARY", "GENERAL", "LOW_SIGNAL"]}, sum(c.values())

    a_share, a_tot = authority_share(a1a2)
    d_share, d_tot = authority_share(dom)
    u_share, u_tot = authority_share(ux)
    print("\n=== AUTHORITY SHARE (fraction of evidence) ===")
    print(f"  {'tier':25} {'postA1A2':>10} {'postdomain':>12} {'postux':>10}")
    for t in ["PRIMARY_AUTHORITATIVE", "REPUTABLE_SECONDARY", "GENERAL", "LOW_SIGNAL"]:
        print(f"  {t:25} {a_share[t]:>10.3f} {d_share[t]:>12.3f} {u_share[t]:>10.3f}")
    print(f"  {'total evidence':25} {a_tot:>10} {d_tot:>12} {u_tot:>10}")

    out = {"postux": ux, "postdomain": dom, "postA1A2": a1a2,
           "authority_share": {"postA1A2": a_share, "postdomain": d_share, "postux": u_share}}
    with open("compare_postux.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print("\n[done] wrote compare_postux.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
