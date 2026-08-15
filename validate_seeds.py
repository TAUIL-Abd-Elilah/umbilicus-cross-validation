"""Score every seed curve against the public reference curves.

Writes `seeds/validation.json` and prints the table that goes in the README.

Only the three hand-drawn curves count towards accuracy. The PHerc1218 curve is
scored but flagged `independent: False`: its generator takes the slice centroid and
running-medians it, which is the same algorithm as the seed, so agreement there
measures implementation consistency and not distance to the true umbilicus. It is
kept in the output precisely so that distinction stays visible rather than being
quietly dropped.
"""

import json
import os

import numpy as np

from evaluate import compare, self_consistency

REFS = {
    "PHerc0125": ("reference/PHerc0125_umbilicus.json", "Sean Johnson (@Bruniss), khartes", True),
    "PHerc0211": ("reference/PHerc0211_umbilicus.json", "Sean Johnson (@Bruniss), khartes", True),
    "PHerc0826": ("reference/PHerc0826_umbilicus.json", "Sean Johnson (@Bruniss), khartes", True),
    "PHerc1218": (
        "../_external/vesuvius-sheet-tools/data/spiral_input_pherc1218/umbilicus.json",
        "IyanDopico/vesuvius-sheet-tools (centroid+running-median: SAME METHOD as the seed)",
        False,
    ),
}

out = {}
print("%-11s %9s %9s %9s | %9s %9s | %s"
      % ("scroll", "median", "p90", "max", "ref med", "ref p90", "reference"))
for name, (path, who, independent) in REFS.items():
    if not os.path.exists(path):
        print(f"{name}: reference not found at {path}")
        continue
    ref = json.load(open(path))["control_points"]
    seed_path = f"seeds/{name}_umbilicus_seed.json"
    if not os.path.exists(seed_path):
        print(f"{name}: no seed")
        continue
    seed = json.load(open(seed_path))["control_points"]

    r = compare(seed, ref)
    s = self_consistency(ref)
    out[name] = {
        "reference": who,
        "independent": independent,
        "reference_points": len(ref),
        "seed_points": len(seed),
        "seed_vs_reference": {k: r[k] for k in ("median", "p90", "max", "mean")},
        "reference_self_consistency": s,
        "scored_points": r["n_reference_points_scored"],
    }
    print("%-11s %9.1f %9.1f %9.1f | %9.1f %9.1f | %s"
          % (name, r["median"], r["p90"], r["max"], s["median"], s["p90"], who))

meds = [v["seed_vs_reference"]["median"] for v in out.values() if v["independent"]]
if meds:
    print()
    print("ACCURACY (hand-drawn references only, n=%d): min %.1f  median %.1f  max %.1f voxels"
          % (len(meds), min(meds), float(np.median(meds)), max(meds)))
    print("PHerc1218 is excluded: same algorithm as the seed, so it measures")
    print("implementation agreement, not accuracy.")

json.dump(out, open("seeds/validation.json", "w"), indent=1)
print("\nwrote seeds/validation.json")
