"""IP-21 smoke test — fires 8 §0.8 matrix questions against prod and records the Stopped event.

Run: python scripts/smoke_ip21.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from typing import Any

import httpx

BASE = "https://novum-prod.duckdns.org"
USER = f"smoke-ip21-{int(time.time())}"

QUESTIONS = [
    ("Q1", "What is the capital of Japan?"),
    ("Q2", "Is PostgreSQL or MongoDB better for a small SaaS application?"),
    ("Q3", "What is the best programming language?"),
    ("Q4", "Is intermittent fasting healthy?"),
    ("Q5", "What are the long-term risks of AI-generated code in enterprise systems?"),
    ("Q6", "Should a high-scale AI platform use event-driven architecture or synchronous microservices?"),
    ("Q7", "What is the most promising approach for long-term memory in autonomous AI agents?"),
    ("Q8", "Could AI systems realistically replace mid-level software engineers within the next 10 years?"),
]

EXPECTED = {
    "Q1": "direct",
    "Q2": "weighted",
    "Q3": "best_effort",
    "Q4": "weighted",
    "Q5": "scenario",
    "Q6": "weighted",
    "Q7": "weighted",
    "Q8": "scenario",
}


async def _retry(coro_factory, attempts: int = 3, delay: float = 3.0):
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            return await coro_factory()
        except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError) as e:
            last_exc = e
            print(f"  retry {i + 1}/{attempts} after {type(e).__name__}: {e}")
            await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]


async def stream_run(client: httpx.AsyncClient, run_id: str, headers: dict[str, str], timeout: float = 600.0) -> dict[str, Any]:
    """Open SSE stream and return the Stopped event payload (or {} on timeout)."""
    url = f"{BASE}/api/runs/{run_id}/events"
    started = time.time()
    async with client.stream("GET", url, headers={**headers, "Accept": "text/event-stream"}, timeout=None) as resp:
        resp.raise_for_status()
        event_lines: list[str] = []
        async for line in resp.aiter_lines():
            if time.time() - started > timeout:
                return {"_error": "timeout"}
            if line == "":
                if event_lines:
                    data_lines = [ln[6:] for ln in event_lines if ln.startswith("data: ")]
                    if data_lines:
                        raw = "\n".join(data_lines)
                        try:
                            payload = json.loads(raw)
                            if payload.get("type") == "Stopped":
                                return payload
                        except json.JSONDecodeError:
                            pass
                    event_lines = []
            else:
                event_lines.append(line)
    return {"_error": "stream_closed"}


async def main() -> None:
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Register (with retry)
        async def _register():
            r = await client.post(f"{BASE}/api/auth/register", json={"username": USER})
            r.raise_for_status()
            return r.json()["token"]

        token = await _retry(_register)
        headers = {"X-Username": USER, "X-Token": token}
        print(f"Registered: {USER}")

        results = []
        for tag, question in QUESTIONS:
            print(f"\n=== {tag}: {question[:60]}... ===")
            t0 = time.time()

            try:
                async def _create_run():
                    r = await client.post(
                        f"{BASE}/api/runs",
                        json={"question": question},
                        headers=headers,
                    )
                    r.raise_for_status()
                    return r.json()["id"]

                run_id = await _retry(_create_run)
                print(f"  run_id={run_id}")

                stopped = await _retry(lambda: stream_run(client, run_id, headers))
            except Exception as e:
                elapsed = time.time() - t0
                print(f"  CLIENT_ERROR ({type(e).__name__}: {e}) ({elapsed:.1f}s)")
                results.append({
                    "tag": tag,
                    "run_id": None,
                    "stop_reason": "client_error",
                    "answer_kind": None,
                    "expected": EXPECTED[tag],
                    "match": "CLIENT_ERROR",
                    "elapsed_s": round(elapsed, 1),
                })
                continue

            elapsed = time.time() - t0
            stop_reason = stopped.get("stop_reason", "?")
            answer_kind = stopped.get("answer_kind", "?")
            expected = EXPECTED[tag]
            match = "OK" if answer_kind == expected else "MISMATCH"
            print(f"  stop_reason={stop_reason} answer_kind={answer_kind} expected={expected} {match} ({elapsed:.1f}s)")
            results.append({
                "tag": tag,
                "run_id": run_id,
                "stop_reason": stop_reason,
                "answer_kind": answer_kind,
                "expected": expected,
                "match": match,
                "elapsed_s": round(elapsed, 1),
            })

        print("\n=== SUMMARY ===")
        print(json.dumps(results, indent=2))
        ok = sum(1 for r in results if r["match"] == "OK")
        print(f"\nMatches: {ok}/{len(results)}")
        if ok < len(results):
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
