import sys
sys.path.insert(0, "scripts")
from compare_postinst import fetch_events

e = fetch_events("24987fd3-5767-4edf-88c4-26e7041707f6")
state_events = {
    "PlanCreated", "PlanCritiqued", "PlanRevised",
    "ClaimCovered", "ClaimUncoverable",
    "HypothesesGenerated", "ToolCalled",
    "AdversarialObjectionsGenerated", "DirectedSubclaimsFromObjections",
    "DraftSynthesized", "JudgeRuled", "MetaStopVerdict",
    "ConfidenceMismatch", "NoProgressDetected", "Stopped",
}
print("Event sequence for Q5:")
n_ev = 0
for ev in e:
    name = ev["event"]
    if name == "EvidenceAdded":
        n_ev += 1
        continue
    if n_ev:
        print(f"   ...({n_ev} EvidenceAdded)...")
        n_ev = 0
    if name in state_events:
        d = ev["data"]
        extras = ""
        if name == "ToolCalled":
            extras = f"tool={d.get('tool_name')} q={(d.get('query') or '')[:40]}"
        elif name == "JudgeRuled":
            extras = f"pass={d.get('passed')} cov={d.get('coverage')} S={d.get('structural_confidence'):.2f}"
        elif name == "Stopped":
            extras = f"reason={d.get('stop_reason')}"
        elif name == "DirectedSubclaimsFromObjections":
            extras = f"added={len(d.get('directed_sub_claims') or [])}"
        print(f"   {name}  {extras}")
if n_ev:
    print(f"   ...({n_ev} EvidenceAdded)...")
