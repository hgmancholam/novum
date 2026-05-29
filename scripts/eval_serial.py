#!/usr/bin/env python3
"""Serial dispatcher for the 8-question baseline re-run.

Dispatches one question, polls until that run's stop_reason is non-null,
then dispatches the next. Designed to avoid the single-worker rate-limit
storm we hit with concurrent dispatch.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE = "https://novum-prod.duckdns.org"
USER = "eval_serial_20260528"
TOKEN = "bc563596b398497c8d6be5a48f51067de0698ba618e67a1290d5c929bf0f82b5"
HEADERS = {
    "Content-Type": "application/json",
    "X-Username": USER,
    "X-Token": TOKEN,
}
QUESTIONS = [
    "What is the capital of Japan?",
    "PostgreSQL or MongoDB for a small SaaS project?",
    "What is the best programming language?",
    "Is intermittent fasting healthy?",
    "What are the long-term risks of using AI-generated code in enterprise systems?",
    "Event-driven architecture vs synchronous microservices for a high-scale AI platform?",
    "What is the most promising approach for long-term memory in autonomous AI agents?",
    "Will AI replace mid-level software engineers in the next 10 years?",
]
POLL_INTERVAL_S = 10
PER_RUN_TIMEOUT_S = 300  # 5 min safety cap per question


def post(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(body).encode(),
        headers=HEADERS,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def get(path: str) -> dict:
    req = urllib.request.Request(f"{BASE}{path}", headers=HEADERS, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def main() -> int:
    results: list[dict] = []
    for i, q in enumerate(QUESTIONS, start=1):
        print(f"[{i}/8] DISPATCH  {q}", flush=True)
        created = post(
            "/api/runs",
            {"question": q, "llm_provider": "anthropic", "confidence_threshold": 0.7},
        )
        run_id = created["id"]
        print(f"        run_id={run_id[:8]}", flush=True)
        start = time.time()
        last_reason = None
        while True:
            elapsed = time.time() - start
            if elapsed > PER_RUN_TIMEOUT_S:
                print(f"        TIMEOUT after {int(elapsed)}s, moving on", flush=True)
                last_reason = "client_timeout"
                break
            time.sleep(POLL_INTERVAL_S)
            try:
                r = get(f"/api/runs/{run_id}")
            except urllib.error.URLError as exc:
                print(f"        poll err: {exc}", flush=True)
                continue
            last_reason = r.get("stop_reason")
            if last_reason is not None:
                print(
                    f"        DONE     stop_reason={last_reason}  elapsed={int(elapsed)}s",
                    flush=True,
                )
                break
        results.append({"run_id": run_id, "question": q, "stop_reason": last_reason})
    print("\n=== SUMMARY ===")
    for r in results:
        print(f"  {r['run_id'][:8]}  {r['stop_reason']:<20} {r['question']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
