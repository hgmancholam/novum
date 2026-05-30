import sys
sys.path.insert(0, "scripts")
from compare_postinst import fetch_events
from collections import Counter

RUNS = [
    ("Q4", "0a046c57-1d3c-43fc-8b24-68588bbe0730"),
    ("Q5", "24987fd3-5767-4edf-88c4-26e7041707f6"),
    ("Q6", "b3f8761a-3858-4043-bdbe-f7c44334d5f6"),
    ("Q8", "208a7c9b-fa6f-4b99-8fe5-0e5f968b7d88"),
]

for lbl, rid in RUNS:
    e = fetch_events(rid)
    c = Counter(ev["event"] for ev in e)
    plans = [ev["data"] for ev in e if ev["event"] == "PlanCreated"]
    ccs = [ev["data"] for ev in e if ev["event"] == "ClaimCovered"]
    ccus = [ev["data"] for ev in e if ev["event"] == "ClaimUncoverable"]
    print(f"\n[{lbl}] {rid[:8]}  total_events={sum(c.values())}")
    print(f"   PlanCreated: {len(plans)}  ClaimCovered: {len(ccs)}  ClaimUncoverable: {len(ccus)}  EvidenceAdded: {c.get('EvidenceAdded',0)}")
    for i, p in enumerate(plans):
        scs = p.get("sub_claims") or []
        print(f"   Plan#{i+1}: {len(scs)} sub_claims: {[s.get('id') for s in scs]}")
    for cc in ccs:
        print(f"     covered: {cc.get('claim_id')} ({cc.get('coverage_rationale')})")
    for cu in ccus:
        print(f"     uncoverable: {cu.get('claim_id')}")
