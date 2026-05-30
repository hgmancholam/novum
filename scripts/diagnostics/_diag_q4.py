import sys
sys.path.insert(0, "scripts")
from compare_postinst import fetch_events

e = fetch_events("0a046c57-1d3c-43fc-8b24-68588bbe0730")
jrs = [ev for ev in e if ev["event"] == "JudgeRuled"]
print("JudgeRuled count:", len(jrs))
for i, jr in enumerate(jrs):
    d = jr["data"]
    print(
        f"  #{i+1} S={d.get('structural_confidence'):.3f} J={d.get('judge_confidence'):.2f} "
        f"passed={d.get('passed')} cov={d.get('coverage')} agr={d.get('agreement')} "
        f"contras={len(d.get('contradictions_detected') or [])} "
        f"blockers={d.get('override_blockers')} bypass={d.get('contra_bypassed')}"
    )

ccs = [ev for ev in e if ev["event"] == "ClaimCovered"]
print(f"\nClaimCovered count: {len(ccs)}")
for cc in ccs:
    print("  ", cc["data"].get("claim_id"), "|", cc["data"].get("coverage_rationale"))

# All events in order
print("\nOrder of state-changing events:")
for ev in e:
    n = ev["event"]
    if n in ("PlanCreated", "ClaimCovered", "DirectedSubclaimsFromObjections",
            "AdversarialObjectionsGenerated", "JudgeRuled", "MetaStopVerdict",
            "DraftSynthesized", "Stopped"):
        d = ev["data"]
        extras = ""
        if n == "PlanCreated":
            extras = f"sub_claims={[c['id'] for c in (d.get('sub_claims') or [])]}"
        elif n == "ClaimCovered":
            extras = f"cid={d.get('claim_id')}"
        elif n == "DirectedSubclaimsFromObjections":
            extras = f"added={[c.get('id') for c in (d.get('directed_sub_claims') or [])]}"
        elif n == "JudgeRuled":
            extras = f"passed={d.get('passed')} cov={d.get('coverage')}"
        elif n == "Stopped":
            extras = f"reason={d.get('stop_reason')}"
        print(f"  {n}  {extras}")
