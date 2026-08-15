"""Flag implausible seed control points before they reach an annotator.

The seed is a body centroid, so it fails wherever the "body" is not the scroll:
near the scan ends the cross-section thins out to fragments, and a detached lump
can win the largest-component test and drag the centroid hundreds or thousands of
voxels sideways.

The reference curves bound what real motion looks like — a median lateral step of
48-170 voxels between control points, p90 up to 342. A step far outside that is the
mask jumping, not the umbilicus moving. Flagged points are marked `score: 0` and
listed in `seeds/qc.json` so the manual pass knows to place them from scratch
rather than trust them.
"""

from __future__ import annotations

import json
import os

import numpy as np

SEEDS = "seeds"
# generous: ~3x the worst reference p90 lateral step, per 1000 z of separation
MAX_STEP_PER_1000Z = 1000.0


def flag(points: list[dict]) -> tuple[list[dict], list[dict]]:
    pts = sorted(points, key=lambda p: p["z"])
    z = np.array([p["z"] for p in pts], float)
    y = np.array([p["y"] for p in pts], float)
    x = np.array([p["x"] for p in pts], float)

    step = np.full(len(pts), np.nan)
    step[1:] = np.hypot(np.diff(y), np.diff(x))
    dz = np.full(len(pts), np.nan)
    dz[1:] = np.diff(z)
    rate = step / np.maximum(dz, 1.0) * 1000.0

    # a point is suspect if it is far from BOTH neighbours: an isolated jump,
    # not a genuine bend that the next point continues
    bad = np.zeros(len(pts), bool)
    for i in range(len(pts)):
        prev_bad = i > 0 and rate[i] > MAX_STEP_PER_1000Z
        next_bad = i + 1 < len(pts) and rate[i + 1] > MAX_STEP_PER_1000Z
        if i == 0:
            bad[i] = next_bad
        elif i == len(pts) - 1:
            bad[i] = prev_bad
        else:
            bad[i] = prev_bad and next_bad

    flagged = []
    for i, p in enumerate(pts):
        if bad[i]:
            p = dict(p)
            p["score"] = 0
            pts[i] = p
            flagged.append(
                {"z": int(z[i]), "y": int(y[i]), "x": int(x[i]),
                 "rate_per_1000z": None if np.isnan(rate[i]) else round(float(rate[i]), 1)}
            )
    return pts, flagged


if __name__ == "__main__":
    report = {}
    for fn in sorted(os.listdir(SEEDS)):
        if not fn.endswith("_umbilicus_seed.json"):
            continue
        path = os.path.join(SEEDS, fn)
        doc = json.load(open(path))
        pts, flagged = flag(doc["control_points"])
        doc["control_points"] = pts
        doc["metadata"]["flagged_points"] = len(flagged)
        doc["metadata"]["flagged_note"] = (
            "score=0 marks a control point where the body-centroid heuristic "
            "jumped; place these manually rather than nudging them."
        )
        json.dump(doc, open(path, "w"), indent=1)
        scroll = fn.replace("_umbilicus_seed.json", "")
        report[scroll] = flagged
        print("%-11s %2d/%d flagged" % (scroll, len(flagged), len(pts)))
    json.dump(report, open(os.path.join(SEEDS, "qc.json"), "w"), indent=1)
    total = sum(len(v) for v in report.values())
    print(f"\n{total} flagged points across {len(report)} scrolls -> seeds/qc.json")
