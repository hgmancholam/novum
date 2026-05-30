"""Resume Q6-Q8 of the 2026-05-30 post-A1A2 eval after terminal exit during Q6."""

from __future__ import annotations

import json
import secrets
import sys
import time
import urllib.error
import urllib.request

API = "https://novum-prod.duckdns.org"

QUESTIONS = [
    "Should a high-scale AI platform use event-driven architecture or synchronous microservices?",
    "What is the most promising approach for long-term memory in autonomous AI agents?",
    "Could AI systems realistically replace mid-level software engineers within the next 10 years?",
]
START_IDX = 6
OUT_FILE = "eval_2026_05_30_postA1A2_q6q8.txt"

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
    last_exc: Exception | None = None
    for attempt in range(1, NET_RETRIES + 1):
        try:
            req = urllib.request.Request(f"{API}{path}", data=data, method=method, headers=h)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if 500 <= e.code < 600 and attempt < NET_RETRIES:
                time.sleep(NET_RETRY_SLEEP_S)
                last_exc = e
                continue
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            time.sleep(NET_RETRY_SLEEP_S)
            last_exc = e
            continue
    assert last_exc is not None
    raise last_exc


def log(line: str, fh) -> None:
    print(line, flush=True)
    fh.write(line + "\n")
    fh.flush()


def main() -> int:
    with open(OUT_FILE, "w", encoding="utf-8") as fh:
        username = f"eval{secrets.token_hex(3)}"
        log(f"[setup] registering user={username}", fh)
        reg = http("POST", "/api/auth/register", body={"username": username})
        token = reg["token"]
        auth = {"X-Username": username, "X-Token": token}

        results: list[dict] = []
        for offset, q in enumerate(QUESTIONS):
            idx = START_IDX + offset
            log(f"\n[Q{idx}/8] POST /api/runs :: {q}", fh)
            created = http(
                "POST",
                "/api/runs",
                body={"question": q, "output_format": "prose", "llm_provider": "anthropic"},
                headers=auth,
            )
            run_id = created["id"]
            log(f"        run_id={run_id}", fh)

            start = time.time()
            last_status = None
            while True:
                elapsed = time.time() - start
                if elapsed > POLL_TIMEOUT_S:
                    log(f"        TIMEOUT after {elapsed:.0f}s", fh)
                    last_status = "timeout"
                    break
                try:
                    state = http("GET", f"/api/runs/{run_id}")
                except Exception as e:
                    log(f"        poll err {e!r}", fh)
                    time.sleep(POLL_INTERVAL_S)
                    continue
                if state.get("stopped_at"):
                    last_status = state.get("stop_reason")
                    log(f"        stopped after {elapsed:.0f}s :: stop_reason={last_status}", fh)
                    break
                time.sleep(POLL_INTERVAL_S)

            results.append(
                {"idx": idx, "question": q, "run_id": run_id, "stop_reason": last_status,
                 "wallclock_s": round(time.time() - start, 1)}
            )
            if offset < len(QUESTIONS) - 1:
                log(f"        sleeping {GAP_BETWEEN_RUNS_S}s before next run...", fh)
                time.sleep(GAP_BETWEEN_RUNS_S)

        log("\n=== SUMMARY ===", fh)
        log(json.dumps(results, indent=2), fh)
    return 0


if __name__ == "__main__":
    sys.exit(main())
