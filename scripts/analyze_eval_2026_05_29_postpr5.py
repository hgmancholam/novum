"""Pull events for each run in the post-PR5 eval batch and aggregate metrics.

Reads run IDs from the SUMMARY block of `eval_2026_05_29_postpr5.txt`,
opens SSE for each, accumulates event counts and key payload fields,
and prints a compact table.

No auth needed (SSE is public-by-URL, RF-05).
"""

from __future__ import annotations

import json
import sys
import urllib.request
from collections import Counter

API = "https://novum-prod.duckdns.org"

RUNS = [
    ("Q1", "e4c87960-f5e8-49f1-87df-29cfa3b9c8b4"),
    ("Q2", "9998cf8b-632e-49b7-8e39-6715638c3dd8"),
    ("Q3", "35dc936d-9b50-4901-b965-d99ef9f0df5f"),
    ("Q4", "8329d496-e586-43b6-8dd5-a2dcec64b706"),
    ("Q5", "08da85a1-0c75-463d-8393-72af0fc3d7ba"),
    ("Q6", "c59701cb-aa74-4e9f-8d6a-727589149965"),
    ("Q7", "1266fb24-6542-4bc4-9e1a-d7616416b4b6"),
    ("Q8", "9496572d-fe24-4e9f-8ce7-9d8ef0137586"),
]


def fetch_events(run_id: str) -> list[dict]:
    """Stream SSE for a stopped run; close after the Stopped frame."""
    url = f"{API}/api/runs/{run_id}/events"
    req = urllib.request.Request(url, headers={"Accept": "text/event-stream"})
    events: list[dict] = []
    with urllib.request.urlopen(req, timeout=120) as resp:
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


def summarize(label: str, run_id: str, events: list[dict]) -> dict:
    counts: Counter[str] = Counter(e["event"] for e in events)
    route = None
    judge_score = None
    structural_score = None
    final_confidence = None
    answer_kind = None
    stop_reason = None
    meta_verdicts: list[str] = []

    for e in events:
        name = e["event"]
        d = e["data"] if isinstance(e["data"], dict) else {}
        if name == "RouteSelected":
            route = d.get("route") or d.get("lane")
        elif name == "JudgeRuled":
            judge_score = d.get("judge_score", judge_score)
            structural_score = d.get("structural_confidence", structural_score)
        elif name == "ConfidenceCalculated":
            final_confidence = d.get("final_confidence", final_confidence)
            structural_score = d.get("structural_confidence", structural_score)
            judge_score = d.get("judge_score", judge_score)
        elif name == "Stopped":
            stop_reason = d.get("stop_reason")
            answer_kind = d.get("answer_kind") or d.get("selected_answer_kind")
            final_confidence = d.get("final_confidence", final_confidence)
        elif name == "MetaStopVerdict":
            meta_verdicts.append(f"{d.get('hook','?')}:{d.get('decision','?')}")

    return {
        "label": label,
        "run_id": run_id[:8],
        "route": route,
        "stop_reason": stop_reason,
        "evidence_added": counts.get("EvidenceAdded", 0),
        "query_reformulated": counts.get("QueryReformulated", 0),
        "tool_called": counts.get("ToolCalled", 0),
        "judge_ruled": counts.get("JudgeRuled", 0),
        "draft_synth": counts.get("DraftSynthesized", 0),
        "lane_escalated": counts.get("LaneEscalated", 0),
        "no_progress": counts.get("NoProgressDetected", 0),
        "meta_verdicts": meta_verdicts,
        "S": structural_score,
        "J": judge_score,
        "final_conf": final_confidence,
        "answer_kind": answer_kind,
        "total_events": sum(counts.values()),
    }


def main() -> int:
    rows: list[dict] = []
    for label, run_id in RUNS:
        print(f"[{label}] {run_id} ...", flush=True)
        try:
            evs = fetch_events(run_id)
        except Exception as exc:  # noqa: BLE001
            print(f"  ERR {exc}", flush=True)
            rows.append({"label": label, "run_id": run_id[:8], "error": str(exc)})
            continue
        row = summarize(label, run_id, evs)
        rows.append(row)
        print(
            f"  route={row['route']} stop={row['stop_reason']} "
            f"S={row['S']} J={row['J']} conf={row['final_conf']} "
            f"kind={row['answer_kind']} ev={row['evidence_added']} "
            f"refmt={row['query_reformulated']} esc={row['lane_escalated']} "
            f"nopg={row['no_progress']} meta={row['meta_verdicts']}",
            flush=True,
        )

    print("\n=== TABLE ===")
    header = (
        f"{'Q':3} {'route':9} {'stop_reason':22} {'S':>5} {'J':>5} "
        f"{'conf':>5} {'kind':18} {'ev':>3} {'rfm':>3} {'esc':>3} {'nop':>3} {'tot':>4}"
    )
    print(header)
    for r in rows:
        if "error" in r:
            print(f"{r['label']:3} ERROR {r['error']}")
            continue
        print(
            f"{r['label']:3} {str(r['route'] or '-'):9} {str(r['stop_reason'] or '-'):22} "
            f"{str(r['S'] or '-'):>5} {str(r['J'] or '-'):>5} "
            f"{str(r['final_conf'] or '-'):>5} {str(r['answer_kind'] or '-'):18} "
            f"{r['evidence_added']:>3} {r['query_reformulated']:>3} "
            f"{r['lane_escalated']:>3} {r['no_progress']:>3} {r['total_events']:>4}"
        )
    print("\n=== META VERDICTS ===")
    for r in rows:
        if r.get("meta_verdicts"):
            print(f"{r['label']}: {r['meta_verdicts']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
