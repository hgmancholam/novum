"""Dump raw payloads for key events on selected runs."""
from __future__ import annotations

import json
import urllib.request

API = "https://novum-prod.duckdns.org"

RUNS = [
    ("Q3", "35dc936d-9b50-4901-b965-d99ef9f0df5f"),
    ("Q4", "8329d496-e586-43b6-8dd5-a2dcec64b706"),
    ("Q5", "08da85a1-0c75-463d-8393-72af0fc3d7ba"),
    ("Q7", "1266fb24-6542-4bc4-9e1a-d7616416b4b6"),
    ("Q8", "9496572d-fe24-4e9f-8ce7-9d8ef0137586"),
]

WANTED = {"JudgeRuled", "MetaStopVerdict", "ConfidenceCalculated", "Stopped", "DraftSynthesized", "RouteSelected", "NoProgressDetected"}


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
    evs = fetch(rid)
    for e in evs:
        if e["event"] in WANTED:
            print(f"-- {e['event']} --")
            print(json.dumps(e["data"], indent=2, ensure_ascii=False)[:1500])
