"""Evaluation driver: run the 8 q-for-testing scenarios against the agent.

Sequence:
  1. Register a one-off evaluation user.
  2. For each of the 8 questions:
       - POST /api/runs (anthropic, prose, threshold 0.7)
       - Poll until `stopped_at` is non-null (or 6 min hard cap).
       - Sleep 60 s before the next question to avoid API throttling.
  3. Emit the run IDs to stdout so the evaluator can query Postgres.
"""

from __future__ import annotations

import json
import secrets
import sys
import time
import urllib.error
import urllib.request

API = "https://novum-prod.duckdns.org"
QUESTIONS = [
    "What is the capital of Japan?",
    "Is PostgreSQL or MongoDB better for a small SaaS application?",
    "What is the best programming language?",
    "Is intermittent fasting healthy?",
    "What are the long-term risks of AI-generated code in enterprise systems?",
    "Should a high-scale AI platform use event-driven architecture or synchronous microservices?",
    "What is the most promising approach for long-term memory in autonomous AI agents?",
    "Could AI systems realistically replace mid-level software engineers within the next 10 years?",
]

POLL_INTERVAL_S = 5
POLL_TIMEOUT_S = 360  # 6 min hard cap per run
GAP_BETWEEN_RUNS_S = 60


def http(method: str, path: str, *, body=None, headers=None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(f"{API}{path}", data=data, method=method, headers=h)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    username = f"eval{secrets.token_hex(3)}"
    print(f"[setup] registering user={username}", flush=True)
    reg = http("POST", "/api/auth/register", body={"username": username})
    token = reg["token"]
    auth_headers = {"X-Username": username, "X-Token": token}

    results: list[dict] = []
    for idx, q in enumerate(QUESTIONS, start=1):
        print(f"\n[Q{idx}/8] POST /api/runs :: {q}", flush=True)
        created = http(
            "POST",
            "/api/runs",
            body={
                "question": q,
                "output_format": "prose",
                "confidence_threshold": 0.7,
                "llm_provider": "anthropic",
            },
            headers=auth_headers,
        )
        run_id = created["id"]
        print(f"        run_id={run_id}", flush=True)

        # Poll until stopped
        start = time.time()
        last_status = None
        while True:
            elapsed = time.time() - start
            if elapsed > POLL_TIMEOUT_S:
                print(f"        TIMEOUT after {elapsed:.0f}s", flush=True)
                last_status = "timeout"
                break
            try:
                state = http("GET", f"/api/runs/{run_id}")
            except urllib.error.HTTPError as e:
                print(f"        poll error {e}", flush=True)
                time.sleep(POLL_INTERVAL_S)
                continue
            if state.get("stopped_at"):
                last_status = state.get("stop_reason")
                print(
                    f"        stopped after {elapsed:.0f}s :: stop_reason={last_status}",
                    flush=True,
                )
                break
            time.sleep(POLL_INTERVAL_S)

        results.append(
            {
                "idx": idx,
                "question": q,
                "run_id": run_id,
                "stop_reason": last_status,
                "wallclock_s": round(time.time() - start, 1),
            }
        )

        if idx < len(QUESTIONS):
            print(f"        sleeping {GAP_BETWEEN_RUNS_S}s before next run...", flush=True)
            time.sleep(GAP_BETWEEN_RUNS_S)

    print("\n=== SUMMARY ===", flush=True)
    print(json.dumps(results, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
