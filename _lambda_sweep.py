"""Sweep the continuity strength over cached score grids.

The point is to find out whether *any* setting of the continuity prior turns the
lasagna evidence into a curve at the reference noise floor, or whether the
evidence is wrong in a way no smoothing can fix.  Running it over cached grids
makes the answer cheap and therefore honest — the stopping decision is measured,
not asserted.
"""

import json
import sys

import numpy as np

from evaluate import compare, self_consistency
from track import viterbi_track

scroll = sys.argv[1] if len(sys.argv) > 1 else "PHerc0211"
d = np.load(f"cache/{scroll}_grids.npz")
grids = [g for g in d["grids"]]
zs = list(d["zs"])
anchors = d["anchors"]
search, step = int(d["search"]), int(d["step"])
off = np.arange(-search, search + 1, step, dtype=np.float64)

ref = json.load(open(f"reference/{scroll}_umbilicus.json"))["control_points"]
seed = json.load(open(f"seeds/{scroll}_umbilicus_seed.json"))["control_points"]
sc = self_consistency(ref)
rs = compare(seed, ref)

print(f"{scroll}: {len(grids)} score grids, search +/-{search} step {step}")
print(f"  reference noise   median {sc['median']:7.1f}  p90 {sc['p90']:7.1f}")
print(f"  centroid seed     median {rs['median']:7.1f}  p90 {rs['p90']:7.1f}")
print()
print("%8s %8s | %8s %8s %8s %8s" % ("lambda", "maxstep", "median", "p90", "max", "ratio"))

best = None
for lam in (0.0, 0.25, 1.0, 4.0, 16.0, 64.0, 256.0):
    for ms in (0.5, 1.0, 2.0):
        ty, tx, info = viterbi_track(grids, zs, off, off, lam=lam, max_step_per_z=ms)
        ty = ty + anchors[:, 0]
        tx = tx + anchors[:, 1]
        pts = [
            {"x": float(x), "y": float(y), "z": int(z), "score": 100}
            for z, y, x in zip(zs, ty, tx)
        ]
        r = compare(pts, ref)
        ratio = float(np.median(info["score_ratio"]))
        print("%8.2f %8.1f | %8.1f %8.1f %8.1f %8.3f"
              % (lam, ms, r["median"], r["p90"], r["max"], ratio))
        if best is None or r["median"] < best[0]:
            best = (r["median"], lam, ms)

print()
print("best: median %.1f at lambda=%.2f max_step_per_z=%.1f" % best)
print("reference noise floor is %.1f; seed is %.1f" % (sc["median"], rs["median"]))
