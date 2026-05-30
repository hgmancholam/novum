"""Compare IP-31 (postdomain, 2026-05-30) vs prior postA1A2 (run4) and baseline.

Adds confidence + unique source hostnames per question.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

API = "https://novum-prod.duckdns.org"

# Baseline (events purged): only stop_reason + wallclock available
BASELINE = [
    ("Q1", "judge_confirmed", 11.6),
    ("Q2", "stopped_by_budget", 100.0),
    ("Q3", "judge_confirmed", 34.0),
    ("Q4", "judge_confirmed", 79.2),
    ("Q5", "judge_confirmed", 95.7),
    ("Q6", "stopped_by_budget", 72.0),
    ("Q7", "stopped_by_budget", 356.6),
    ("Q8", "stopped_by_budget", 284.4),
]

PREV_POST = [
    ("Q1", "79737678-270a-426b-9981-807bc7098386"),
    ("Q2", "ccbd12cc-5570-4e26-99ec-e1fe64a3910a"),
    ("Q3", "ae3a8648-079d-441c-bab3-372b54d6f997"),
    ("Q4", "9c713a41-6920-4dc3-a463-b844c0f1ab56"),
    ("Q5", "85130b57-1cb1-4b0f-a761-807066660a91"),
    ("Q6", "749ceb67-81dd-4c40-b9c8-43a78f81e530"),
    ("Q7", "c5b1ea1c-39e2-4128-9d61-d477b877f252"),
    ("Q8", "d9b53537-0944-42ca-aeee-15d8e5585553"),
]

POST = [
    ("Q1", "2e55036d-18d6-421f-93ed-7efce26c5216", 22.8),
    ("Q2", "46736c54-8252-40ec-b0ed-6cd4da85bcf5", 79.0),
    ("Q3", "f1ddb63d-954b-478f-932a-a91724b3fb1a", 39.6),
    ("Q4", "6d379ce5-62ff-40df-8fce-45a840625279", 106.7),
    ("Q5", "87afe243-171f-45ae-8cea-9b8271e9f5ea", 72.1),
    ("Q6", "f906ab84-bb7c-4cdb-b9af-3e48afdfe52b", 106.7),
    ("Q7", "3feaf0b7-a9f2-4736-9e5b-aea8ebda4eb0", 162.4),
    ("Q8", "a2243165-9c20-463a-b8ed-e805c635ddb9", 117.7),
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
    counts: Counter[str] = Counter(e["event"] for e in events)
    route = stop_reason = answer_kind = domain = None
    judge_score = structural_score = final_confidence = None
    prompt_tokens = completion_tokens = 0
    cost_usd = 0.0
    llm_calls = 0
    src_counter: Counter[str] = Counter()
    host_counter: Counter[str] = Counter()
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
        elif name == "DraftSynthesized":
            if not prose_excerpt:
                prose = (d.get("answer") or d.get("prose") or "")[:240]
                prose_excerpt = prose
        elif name == "CostIncurred":
            llm_calls += 1
            prompt_tokens += int(d.get("prompt_tokens", 0) or 0)
            completion_tokens += int(d.get("completion_tokens", 0) or 0)
            cost_usd += float(d.get("cost_usd", 0.0) or 0.0)
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
        "evidence_by_src": dict(src_counter),
        "host_counter": dict(host_counter),
        "unique_hosts": len(host_counter),
        "llm_calls": llm_calls,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cost_usd": cost_usd,
        "prose_excerpt": prose_excerpt,
        "total_events": sum(counts.values()),
    }


def main() -> int:
    new_rows: list[dict] = []
    prev_rows: list[dict] = []
    print("[fetch] new (postdomain)...")
    for label, rid, wc in POST:
        print(f"  [{label}] {rid[:8]} ...", flush=True)
        try:
            evs = fetch_events(rid)
            new_rows.append(summarize(label, rid, wc, evs))
        except Exception as exc:
            print(f"    ERROR: {exc}", flush=True)
            new_rows.append({"label": label, "run_id": rid[:8], "error": str(exc)})

    print("[fetch] prev (postA1A2)...")
    for label, rid in PREV_POST:
        print(f"  [{label}] {rid[:8]} ...", flush=True)
        try:
            evs = fetch_events(rid)
            prev_rows.append(summarize(label, rid, None, evs))
        except Exception as exc:
            print(f"    ERROR: {exc}", flush=True)
            prev_rows.append({"label": label, "run_id": rid[:8], "error": str(exc)})

    base_counter = Counter(r[1] for r in BASELINE)
    new_counter = Counter(r["stop_reason"] for r in new_rows if "error" not in r)
    prev_counter = Counter(r["stop_reason"] for r in prev_rows if "error" not in r)

    print("\n=== STOP REASON (baseline → prev (postA1A2) → new (postdomain)) ===")
    keys = sorted(set(base_counter) | set(new_counter) | set(prev_counter))
    print(f"  {'reason':25} {'baseline':>10} {'postA1A2':>10} {'postdomain':>12}")
    for k in keys:
        print(f"  {k:25} {base_counter.get(k, 0):>10} {prev_counter.get(k, 0):>10} {new_counter.get(k, 0):>12}")

    print("\n=== PER QUESTION (new run) ===")
    for r in new_rows:
        if "error" in r:
            print(f"  {r['label']:3} ERROR {r['error']}")
            continue
        print(
            f"  {r['label']:3} {str(r['route'] or '-'):9} dom={str(r['domain'] or '-'):16} "
            f"{str(r['stop_reason'] or '-')[:22]:22} "
            f"S={('-' if r['S'] is None else f'{r['S']:.2f}'):>5} "
            f"J={('-' if r['J'] is None else f'{r['J']:.2f}'):>5} "
            f"conf={('-' if r['conf'] is None else f'{r['conf']:.2f}'):>5} "
            f"ev={r['evidence_total']:>3} hosts={r['unique_hosts']:>2} "
            f"$={r['cost_usd']:.4f} t={r['wallclock_s']:.0f}s"
        )

    print("\n=== CONFIDENCE PER QUESTION (prev → new) ===")
    by_label_prev = {r["label"]: r for r in prev_rows if "error" not in r}
    print(f"  {'Q':3} {'prevConf':>10} {'newConf':>10} {'prevHosts':>10} {'newHosts':>10}")
    for r in new_rows:
        if "error" in r:
            continue
        p = by_label_prev.get(r["label"], {})
        pc = p.get("conf")
        ph = p.get("unique_hosts", 0)
        print(
            f"  {r['label']:3} "
            f"{('-' if pc is None else f'{pc:.2f}'):>10} "
            f"{('-' if r['conf'] is None else f'{r['conf']:.2f}'):>10} "
            f"{ph:>10} {r['unique_hosts']:>10}"
        )

    print("\n=== SOURCES PER QUESTION (new) ===")
    for r in new_rows:
        if "error" in r:
            continue
        hosts = sorted(r["host_counter"].items(), key=lambda kv: -kv[1])
        host_str = ", ".join(f"{h}×{c}" for h, c in hosts[:10])
        print(f"  {r['label']:3} ({r['unique_hosts']} hosts): {host_str}")

    print("\n=== SOURCES PER QUESTION (prev / postA1A2) ===")
    for r in prev_rows:
        if "error" in r:
            continue
        hosts = sorted(r["host_counter"].items(), key=lambda kv: -kv[1])
        host_str = ", ".join(f"{h}×{c}" for h, c in hosts[:10])
        print(f"  {r['label']:3} ({r['unique_hosts']} hosts): {host_str}")

    # JSON dump for downstream analysis
    out = {
        "new": new_rows,
        "prev": prev_rows,
    }
    with open("compare_postdomain.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print("\n[done] wrote compare_postdomain.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
