"""Dump key events for Q2 and Q6 (post-PR-8 eval reincidents)."""
from __future__ import annotations

import json
import urllib.request

API = "https://novum-prod.duckdns.org"

RUNS = [
    ("Q2", "2554c7d3-0293-4e03-8cd9-1dd921f2282a"),
    ("Q6", "178f1828-1dee-490c-a63f-bec4f20a83a1"),
]

WANTED = {
    "JudgeRuled",
    "MetaStopVerdict",
    "Stopped",
    "DraftSynthesized",
    "RouteSelected",
    "NoProgressDetected",
    "EvidenceAdded",
    "AgentErrored",
    "JudgeProviderDegraded",
}


def fetch(run_id: str) -> list[dict]:
    url = f"{API}/api/runs/{run_id}/events"
    req = urllib.request.Request(url, headers={"Accept": "text/event-stream"})
    out: list[dict] = []
    with urllib.request.urlopen(req, timeout=120) as resp:
        ev = None
        buf: list[str] = []
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").rstrip("\n").rstrip("\r")
            if line == "":
                if ev and buf:
                    try:
                        payload = json.loads("\n".join(buf))
                    except json.JSONDecodeError:
                        payload = {"_raw": "\n".join(buf)}
                    out.append({"event": ev, "data": payload})
                    if ev == "Stopped":
                        break
                ev = None
                buf = []
                continue
            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                ev = line[6:].strip()
            elif line.startswith("data:"):
                buf.append(line[5:].lstrip())
    return out


for label, rid in RUNS:
    print(f"\n========== {label} ({rid[:8]}) ==========")
    events = fetch(rid)
    ev_count = sum(1 for e in events if e["event"] == "EvidenceAdded")
    print(f"-- total events: {len(events)} (EvidenceAdded={ev_count}) --")
    for e in events:
        if e["event"] in WANTED and e["event"] != "EvidenceAdded":
            print(f"-- {e['event']} --")
            print(json.dumps(e["data"], indent=2, ensure_ascii=False)[:2000])
