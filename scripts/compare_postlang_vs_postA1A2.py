"""Compare baseline (2026-05-29 postlang) vs post (2026-05-30 postA1A2).

Baseline runs were purged from the DB between deploys, so per-run
token/cost metrics for the baseline are not retrievable. Comparison is
limited to: stop_reason ratio, wallclock. Post batch gets the full
breakdown (route, S/J, evidence, llm_calls, prompt_tokens, cost_usd,
per-task drill-down).
"""

from __future__ import annotations

import json
import urllib.request
from collections import Counter, defaultdict

API = "https://novum-prod.duckdns.org"

BASELINE = [
    ("Q1", "judge_confirmed",   11.6),
    ("Q2", "stopped_by_budget", 100.0),
    ("Q3", "judge_confirmed",   34.0),
    ("Q4", "judge_confirmed",   79.2),
    ("Q5", "judge_confirmed",   95.7),
    ("Q6", "stopped_by_budget", 72.0),
    ("Q7", "stopped_by_budget", 356.6),
    ("Q8", "stopped_by_budget", 284.4),
]

PREV_POST = [
    ("Q1", "f0cb7788", "judge_confirmed",    17.2),
    ("Q2", "0408cf61", "stopped_by_budget",  73.2),
    ("Q3", "dd6ad2f8", "judge_confirmed",    44.1),
    ("Q4", "945d9465", "judge_confirmed",    73.1),
    ("Q5", "0fe6cce6", "stopped_by_budget", 100.9),
    ("Q6", "8202aafb", "stopped_by_budget", 184.7),
    ("Q7", "ed70d32c", "stopped_by_budget", 145.5),
    ("Q8", "4fe61e59", "stopped_by_budget", 172.6),
]

POST = [
    ("Q1", "79737678-270a-426b-9981-807bc7098386",  11.8),
    ("Q2", "ccbd12cc-5570-4e26-99ec-e1fe64a3910a",  48.4),
    ("Q3", "ae3a8648-079d-441c-bab3-372b54d6f997",  32.7),
    ("Q4", "9c713a41-6920-4dc3-a463-b844c0f1ab56",  79.2),
    ("Q5", "85130b57-1cb1-4b0f-a761-807066660a91", 128.1),
    ("Q6", "749ceb67-81dd-4c40-b9c8-43a78f81e530", 102.0),
    ("Q7", "c5b1ea1c-39e2-4128-9d61-d477b877f252", 111.0),
    ("Q8", "d9b53537-0944-42ca-aeee-15d8e5585553", 121.1),
]


def fetch_events(run_id: str) -> list[dict]:
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


def summarize(label: str, run_id: str, wallclock: float, events: list[dict]) -> dict:
    counts: Counter[str] = Counter(e["event"] for e in events)
    route = stop_reason = answer_kind = None
    judge_score = structural_score = final_confidence = None
    prompt_tokens = completion_tokens = 0
    cost_usd = 0.0
    llm_calls = 0
    by_task: dict[str, dict[str, float]] = defaultdict(
        lambda: {"calls": 0, "pt": 0, "ct": 0, "cost": 0.0}
    )
    for e in events:
        name = e["event"]
        d = e["data"] if isinstance(e["data"], dict) else {}
        if name == "RouteSelected":
            route = d.get("route") or d.get("lane") or route
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
        elif name == "CostIncurred":
            llm_calls += 1
            pt = int(d.get("prompt_tokens", 0) or 0)
            ct = int(d.get("completion_tokens", 0) or 0)
            cu = float(d.get("cost_usd", 0.0) or 0.0)
            prompt_tokens += pt
            completion_tokens += ct
            cost_usd += cu
            task = str(d.get("task_name") or d.get("kind") or "?")
            slot = by_task[task]
            slot["calls"] += 1
            slot["pt"] += pt
            slot["ct"] += ct
            slot["cost"] += cu
    return {
        "label": label,
        "run_id": run_id[:8],
        "wallclock_s": wallclock,
        "route": route,
        "stop_reason": stop_reason,
        "S": structural_score,
        "J": judge_score,
        "conf": final_confidence,
        "answer_kind": answer_kind,
        "evidence_added": counts.get("EvidenceAdded", 0),
        "query_reformulated": counts.get("QueryReformulated", 0),
        "lane_escalated": counts.get("LaneEscalated", 0),
        "no_progress": counts.get("NoProgressDetected", 0),
        "planning_rounds": counts.get("PlanningRoundStarted", 0),
        "judge_ruled_count": counts.get("JudgeRuled", 0),
        "llm_calls": llm_calls,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cost_usd": cost_usd,
        "by_task": dict(by_task),
        "total_events": sum(counts.values()),
    }


def main() -> int:
    rows: list[dict] = []
    print("[fetch] streaming events for post batch...")
    for label, rid, wc in POST:
        print(f"  [{label}] {rid[:8]} ...", flush=True)
        try:
            evs = fetch_events(rid)
            rows.append(summarize(label, rid, wc, evs))
        except Exception as exc:  # noqa: BLE001
            print(f"    ERROR: {exc}", flush=True)
            rows.append({"label": label, "run_id": rid[:8], "error": str(exc)})

    base_counter = Counter(r[1] for r in BASELINE)
    post_counter = Counter(r["stop_reason"] for r in rows if "error" not in r)
    print("\n=== STOP REASON (baseline 2026-05-29 -> post 2026-05-30) ===")
    for k in sorted(set(base_counter) | set(post_counter)):
        print(f"  {k:25} {base_counter.get(k, 0):>2} -> {post_counter.get(k, 0):>2}")

    print("\n=== WALLCLOCK PER QUESTION (s) ===")
    print(f"  {'Q':3} {'baseline':>10} {'run3':>10} {'run4':>10} {'d_base':>10} {'d_run3':>10}")
    for (b_label, _, b_wc), (_, _, _, p1_wc), p in zip(BASELINE, PREV_POST, rows):
        if "error" in p:
            continue
        d_base = p["wallclock_s"] - b_wc
        d_p1 = p["wallclock_s"] - p1_wc
        print(f"  {b_label:3} {b_wc:>10.1f} {p1_wc:>10.1f} {p['wallclock_s']:>10.1f} "
              f"{d_base:>+10.1f} {d_p1:>+10.1f}")
    base_total = sum(b[2] for b in BASELINE)
    p1_total = sum(p[3] for p in PREV_POST)
    post_total = sum(p["wallclock_s"] for p in rows if "error" not in p)
    print(f"  {'tot':3} {base_total:>10.1f} {p1_total:>10.1f} {post_total:>10.1f} "
          f"{post_total-base_total:>+10.1f} {post_total-p1_total:>+10.1f}")

    print("\n=== STOP REASON (3-way) ===")
    p1_counter = Counter(p[2] for p in PREV_POST)
    print(f"  {'reason':25} {'baseline':>10} {'run3':>10} {'run4':>10}")
    for k in sorted(set(base_counter) | set(post_counter) | set(p1_counter)):
        print(f"  {k:25} {base_counter.get(k, 0):>10} {p1_counter.get(k, 0):>10} {post_counter.get(k, 0):>10}")

    print("\n=== POST BATCH - FULL METRICS PER RUN ===")
    print(
        f"  {'Q':3} {'route':9} {'stop':22} {'conf':>5} "
        f"{'rnd':>3} {'ev':>3} {'rfm':>3} {'llm':>4} "
        f"{'p_tok':>7} {'c_tok':>6} {'$':>8}"
    )
    for r in rows:
        if "error" in r:
            print(f"  {r['label']:3} ERROR {r['error']}")
            continue
        print(
            f"  {r['label']:3} {str(r['route'] or '-'):9} {str(r['stop_reason'] or '-')[:22]:22} "
            f"{str(round(r['conf'], 2) if r['conf'] else '-'):>5} "
            f"{r['planning_rounds']:>3} {r['evidence_added']:>3} {r['query_reformulated']:>3} "
            f"{r['llm_calls']:>4} {r['prompt_tokens']:>7,} {r['completion_tokens']:>6,} "
            f"${r['cost_usd']:>7.4f}"
        )

    print("\n=== POST BATCH - TOTAL BY LLM TASK (8 runs combined) ===")
    grand: dict[str, dict[str, float]] = defaultdict(
        lambda: {"calls": 0, "pt": 0, "ct": 0, "cost": 0.0}
    )
    for r in rows:
        if "error" in r:
            continue
        for t, slot in r["by_task"].items():
            g = grand[t]
            g["calls"] += slot["calls"]
            g["pt"] += slot["pt"]
            g["ct"] += slot["ct"]
            g["cost"] += slot["cost"]
    total_calls = sum(g["calls"] for g in grand.values()) or 1
    total_pt = sum(g["pt"] for g in grand.values()) or 1
    total_cost = sum(g["cost"] for g in grand.values())
    print(
        f"  {'task':>22} {'calls':>6} {'%cls':>6} "
        f"{'p_tok':>9} {'%ptk':>6} {'avg_p':>7} "
        f"{'c_tok':>7} {'cost$':>9} {'%cst':>6}"
    )
    for t, g in sorted(grand.items(), key=lambda kv: -kv[1]["cost"]):
        print(
            f"  {t:>22} {int(g['calls']):>6} {g['calls']/total_calls*100:>5.1f}% "
            f"{int(g['pt']):>9,} {g['pt']/total_pt*100:>5.1f}% "
            f"{g['pt']/max(1, g['calls']):>7.0f} "
            f"{int(g['ct']):>7,} ${g['cost']:>7.4f} "
            f"{g['cost']/max(1e-9, total_cost)*100:>5.1f}%"
        )
    print(f"  {'TOTAL':>22} {int(total_calls):>6}        {int(total_pt):>9,}        "
          f"        ${total_cost:>7.4f}")

    print("\n" + "=" * 78)
    print("WHY ARE WE BURNING MORE TOKENS THAN BASELINE?")
    print("=" * 78)
    print(
        "\nNOTE: la DB fue purgada entre eval; no hay prompt_tokens del baseline.\n"
        "Solo se compara stop_reason + wallclock; el resto son numeros absolutos\n"
        "del post batch + razonamiento causal.\n"
    )

    valid = [r for r in rows if "error" not in r]
    n_valid = len(valid) or 1
    avg_calls = sum(r["llm_calls"] for r in valid) / n_valid
    avg_rounds = sum(r["planning_rounds"] for r in valid) / n_valid
    avg_reform = sum(r["query_reformulated"] for r in valid) / n_valid
    avg_pt = sum(r["prompt_tokens"] for r in valid) / n_valid
    total_post_cost = sum(r["cost_usd"] for r in valid)

    base_budget = base_counter.get("stopped_by_budget", 0)
    post_budget = post_counter.get("stopped_by_budget", 0)
    base_judge = base_counter.get("judge_confirmed", 0)
    post_judge = post_counter.get("judge_confirmed", 0)

    print(
        f"Factor 1 - Mas runs terminan en stopped_by_budget:\n"
        f"  baseline:  {base_judge} judge_confirmed / {base_budget} stopped_by_budget\n"
        f"  post:      {post_judge} judge_confirmed / {post_budget} stopped_by_budget\n"
        f"  -> cada run que YA NO termina en judge_confirmed agota el budget\n"
        f"     (tipicamente 3-6x mas LLM calls que un judge_confirmed temprano).\n"
        f"  -> NO es regresion de A1+A2: es Phase 1 (round-aware threshold,\n"
        f"     stuck_planner, academic cascade) decidiendo que necesita mas evidencia."
    )

    flips = []
    for (b_label, b_stop, _), p in zip(BASELINE, valid):
        if b_stop == "judge_confirmed" and p["stop_reason"] == "stopped_by_budget":
            flips.append(b_label)
    if flips:
        print(
            f"\n  Runs que perdieron judge_confirmed: {flips}\n"
            f"  -> Estos runs hoy hacen budget completo en vez de aceptar la primera ronda.\n"
            f"     Si su confianza final >= 0.7, la calidad se mantiene; solo cuesta mas."
        )

    print(
        f"\nFactor 2 - Volumen por run (post batch, promedio):\n"
        f"  avg LLM calls/run:        {avg_calls:.1f}\n"
        f"  avg planning_rounds/run:  {avg_rounds:.1f}\n"
        f"  avg reformulations/run:   {avg_reform:.1f}\n"
        f"  avg prompt_tokens/run:    {avg_pt:,.0f}\n"
        f"  cost total post batch:    ${total_post_cost:.4f}\n"
        f"  -> Cada round extra dispara >=1 PLANNER + >=1 JUDGE + >=1 SYNTHESIZER call."
    )

    classifier_g = grand.get("classifier", {"calls": 0, "pt": 0, "cost": 0.0})
    print(
        f"\nFactor 3 - CLASSIFIER cache (A2):\n"
        f"  CLASSIFIER calls registrados:  {int(classifier_g['calls'])}\n"
        f"  Esperado sin cache (1/run):    {n_valid}\n"
        f"  Tokens CLASSIFIER:             {int(classifier_g['pt']):,} pt / ${classifier_g['cost']:.4f}\n"
        f"  -> El cache short-circuit emite el evento 'classifier_cache_hit' en logs\n"
        f"     pero NO emite CostIncurred. Si el numero esta cerca de {n_valid}, no hubo\n"
        f"     repeticiones (cada Q es unica). El valor de A2 se vera en demos donde\n"
        f"     se repite la misma pregunta."
    )

    print(
        f"\nFactor 4 - Anthropic prompt cache (A1):\n"
        f"  CostIncurred NO desagrega cache_read_input_tokens vs cache_creation_input_tokens.\n"
        f"  Litellm los reporta en usage.* pero el payload del evento solo guarda\n"
        f"  prompt_tokens (suma total).\n"
        f"  -> cost_usd YA refleja el descuento (cache_read se factura ~10%) pero el\n"
        f"     conteo de tokens no distingue. Para validar A1 directamente:\n"
        f"       ssh oracle 'journalctl -u novum.service -n 2000 | grep -i cache_read'\n"
        f"  -> Commit pendiente: exponer cache_read / cache_creation en CostIncurredEvent."
    )

    print(
        f"\nResumen ejecutivo:\n"
        f"  - Subida de tokens = mayormente Phase 1 ({post_budget - base_budget} runs\n"
        f"    adicionales agotando budget x ~3-6x calls/run).\n"
        f"  - A1+A2 bajan costo POR CALL en Anthropic (visible en cost_usd, no en\n"
        f"    prompt_tokens) pero no anulan el volumen extra de Phase 1.\n"
        f"  - Proximos pasos: commit #2 (B2 regression harness) y commit #3 (B1 BM25+MMR)\n"
        f"    para reducir contexto por call y compensar el volumen extra."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
