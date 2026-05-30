import sys
from collections import Counter
sys.path.insert(0, "scripts")
from compare_postinst import fetch_events

e = fetch_events("24987fd3-5767-4edf-88c4-26e7041707f6")
tc_counter = Counter()
conf_per_cid = {}
for ev in e:
    if ev["event"] == "EvidenceAdded":
        d = ev["data"]
        cid = d.get("target_claim_id")
        tc_counter[cid] += 1
        conf_per_cid.setdefault(cid, []).append(d.get("confidence"))
print("EvidenceAdded target_claim_id distribution:")
for cid, n in tc_counter.most_common():
    confs = conf_per_cid[cid]
    avg = sum(confs)/len(confs) if confs else 0
    print(f"  {cid}: n={n}  avg_conf={avg:.3f}")

print("\nPlan sub_claim IDs:")
for ev in e:
    if ev["event"] == "PlanCreated":
        for c in ev["data"].get("sub_claims") or []:
            print(f"  id={c.get('id')!r}  text={c.get('text')[:80]}")

# Also check DirectedSubclaimsFromObjections (might inject new ids)
print("\nDirectedSubclaimsFromObjections:")
for ev in e:
    if ev["event"] == "DirectedSubclaimsFromObjections":
        for c in ev["data"].get("directed_sub_claims") or []:
            print(f"  id={c.get('id')!r}")
