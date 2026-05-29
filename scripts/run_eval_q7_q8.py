"""Run only Q7 and Q8 of the 2026-05-29 battery."""

from __future__ import annotations

import json
import secrets
import sys
import time
import urllib.error
import urllib.request

API = "https://novum-prod.duckdns.org"
QUESTIONS = [
    "What is the most promising approach for long-term memory in autonomous AI agents?",
    "Could AI systems realistically replace mid-level software engineers within the next 10 years?",
]

POLL_INTERVAL_S = 5
POLL_TIMEOUT_S = 600
GAP_BETWEEN_RUNS_S = 60
NET_RETRIES = 6
NET_RETRY_SLEEP_S = 10


def http(method: str, path: str, *, body=None, headers=None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    last_err: Exception | None = None
    for attempt in range(NET_RETRIES):
        try:
            req = urllib.request.Request(f"{API}{path}", data=data, method=method, headers=h)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if 500 <= e.code < 600 and attempt < NET_RETRIES - 1:
                last_err = e
                time.sleep(NET_RETRY_SLEEP_S)
                continue
            raise
        except urllib.error.URLError as e:
            last_err = e
            if attempt < NET_RETRIES - 1:
                time.sleep(NET_RETRY_SLEEP_S)
                continue
            raise
    assert last_err is not None
    raise last_err


def main() -> int:
    username = f"eval{secrets.token_hex(3)}"
    print(f"[setup] registering user={username}", flush=True)
    reg = http("POST", "/api/auth/register", body={"username": username})
    token = reg["token"]
    auth_headers = {"X-Username": username, "X-Token": token}

    for idx, q in enumerate(QUESTIONS, start=7):
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
        while True:
            elapsed = time.time() - start
            if elapsed > POLL_TIMEOUT_S:
                print(f"        TIMEOUT after {elapsed:.0f}s", flush=True)
                break
            try:
                state = http("GET", f"/api/runs/{run_id}")
            except (urllib.error.HTTPError, urllib.error.URLError) as e:
                print(f"        poll error {e}", flush=True)
                time.sleep(POLL_INTERVAL_S)
                continue
            if state.get("stopped_at"):
                print(
                    f"        stopped after {elapsed:.0f}s :: stop_reason={state.get('stop_reason')}",
                    flush=True,
                )
                break
            time.sleep(POLL_INTERVAL_S)

        if idx < 8:
            print(f"        sleeping {GAP_BETWEEN_RUNS_S}s before next run...", flush=True)
            time.sleep(GAP_BETWEEN_RUNS_S)

    return 0


if __name__ == "__main__":
    sys.exit(main())
