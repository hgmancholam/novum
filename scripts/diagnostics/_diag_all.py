"""Pull JudgeRuled + override telemetry for every postcontra run.

Diagnoses how often each gate (S, cov, agr, contras) blocks override
across all judge attempts of each run.
"""
import sys
sys.path.insert(0, "scripts")
from compare_postinst import fetch_events

RUNS = [
    ("Q1", "5b0c35c6-9989-4fd1-b5bc-f1826a0fd53f"),
    ("Q2", "67fecf12-3ec9-4929-9c8d-8992495661aa"),
    ("Q3", "34888004-0a45-4c18-ba92-63e8d7b8e912"),
    ("Q4", "0a046c57-1d3c-43fc-8b24-68588bbe0730"),
    ("Q5", "24987fd3-5767-4edf-88c4-26e7041707f6"),
    ("Q6", "b3f8761a-3858-4043-bdbe-f7c44334d5f6"),
    ("Q7", "2ef1e2cd-3164-42d5-a1be-5a083ac5b2c6"),
    ("Q8", "208a7c9b-fa6f-4b99-8fe5-0e5f968b7d88"),
]

for lbl, rid in RUNS:
    e = fetch_events(rid)
    jrs = [ev for ev in e if ev["event"] == "JudgeRuled"]
    stop = next((ev["data"].get("stop_reason") for ev in e if ev["event"] == "Stopped"), "?")
    print(f"\n[{lbl}] {rid[:8]}  stop={stop}  judge_attempts={len(jrs)}")
    peak_S = peak_cov = peak_agr = 0.0
    peak_eligible = False
    for i, jr in enumerate(jrs):
        d = jr["data"]
        s = d.get("structural_confidence") or 0
        cov = d.get("coverage") if d.get("coverage") is not None else "-"
        agr = d.get("agreement") if d.get("agreement") is not None else "-"
        passed = d.get("passed")
        contras = len(d.get("contradictions_detected") or [])
        blockers = d.get("override_blockers")
        bypass = d.get("contra_bypassed")
        elig = d.get("override_eligible")
        cov_f = float(cov) if isinstance(cov, (int, float)) else 0
        agr_f = float(agr) if isinstance(agr, (int, float)) else 0
        peak_S = max(peak_S, s)
        peak_cov = max(peak_cov, cov_f)
        peak_agr = max(peak_agr, agr_f)
        if elig:
            peak_eligible = True
        print(f"   #{i+1} S={s:.3f} cov={cov} agr={agr} pass={passed} "
              f"contras={contras} elig={elig} bypass={bypass} blockers={blockers}")
    print(f"   PEAK: S={peak_S:.3f} cov={peak_cov:.2f} agr={peak_agr:.2f} ever_eligible={peak_eligible}")
