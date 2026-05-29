"""Resume eval battery from Q3..Q8 with retry-on-network-error."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

API = "https://novum-prod.duckdns.org"

# Reuse the user registered by the previous run so all runs share an owner.
USERNAME = "evalbe024e"
TOKEN_FILE = "eval_user_token.txt"

QUESTIONS = [
    "What is the best programming language?",
    "Is intermittent fasting healthy?",
    "What are the long-term risks of AI-generated code in enterprise systems?",
    "Should a high-scale AI platform use event-driven architecture or synchronous microservices?",
    "What is the most promising approach for long-term memory in autonomous AI agents?",
    "Could AI systems realistically replace mid-level software engineers within the next 10 years?",
]
START_IDX = 3  # Q3..Q8 (Q1 done; Q2 in flight already)

POLL_INTERVAL_S = 5
POLL_TIMEOUT_S = 360
GAP_BETWEEN_RUNS_S = 60
NET_RETRIES = 6
NET_RETRY_SLEEP_S = 10


def http(method: str, path: str, *, body=None, headers=None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    last_exc: Exception | None = None
    for attempt in range(1, NET_RETRIES + 1):
        try:
            req = urllib.request.Request(
                f"{API}{path}", data=data, method=method, headers=h
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if 500 <= e.code < 600 and attempt < NET_RETRIES:
                print(f"        http {e.code}, retry {attempt}/{NET_RETRIES}", flush=True)
                time.sleep(NET_RETRY_SLEEP_S)
                last_exc = e
                continue
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            print(f"        net err ({e!r}), retry {attempt}/{NET_RETRIES}", flush=True)
            time.sleep(NET_RETRY_SLEEP_S)
            last_exc = e
            continue
    assert last_exc is not None
    raise last_exc


def main(token: str) -> int:
    auth_headers = {"X-Username": USERNAME, "X-Token": token}
    results: list[dict] = []
    for offset, q in enumerate(QUESTIONS):
        idx = START_IDX + offset
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
            except Exception as e:
                print(f"        poll err {e!r}; continuing", flush=True)
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

        if offset < len(QUESTIONS) - 1:
            print(f"        sleeping {GAP_BETWEEN_RUNS_S}s before next run...", flush=True)
            time.sleep(GAP_BETWEEN_RUNS_S)

    print("\n=== RESUME SUMMARY ===", flush=True)
    print(json.dumps(results, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: resume_eval.py <token>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
