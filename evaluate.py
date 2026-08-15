"""Compare a picked umbilicus against a public reference curve.

Metric (frozen in PROTOCOL.md before any picking): for each reference control
point, the distance from the reference (y, x) to the picked curve *interpolated
at that z*, in full-resolution voxels.  Only reference points inside the picked
curve's z range are scored, since outside it the comparison would be measuring
extrapolation rather than agreement.
"""

from __future__ import annotations

import argparse
import glob
import json
import os

import numpy as np

from montage import picks_to_points


def load_picked(scroll: str, picks_dir: str = "picks") -> list[dict]:
    """Assemble every recorded part of a scroll into one control point list."""
    pts: list[dict] = []
    for pf in sorted(glob.glob(os.path.join(picks_dir, f"{scroll}_p*.json"))):
        rec = json.load(open(pf))
        manifest = json.load(open(rec["manifest"]))
        picks = {int(k): tuple(v) for k, v in rec["picks"].items()}
        pts.extend(picks_to_points(manifest, picks))
    return sorted(pts, key=lambda p: p["z"])


def curve(points: list[dict]):
    z = np.array([p["z"] for p in points], float)
    y = np.array([p["y"] for p in points], float)
    x = np.array([p["x"] for p in points], float)
    o = np.argsort(z)
    return z[o], y[o], x[o]


def compare(picked: list[dict], reference: list[dict]) -> dict:
    pz, py, px = curve(picked)
    rz, ry, rx = curve(reference)
    inside = (rz >= pz.min()) & (rz <= pz.max())
    rz, ry, rx = rz[inside], ry[inside], rx[inside]
    if rz.size == 0:
        raise ValueError("no reference points inside the picked z range")
    iy = np.interp(rz, pz, py)
    ix = np.interp(rz, pz, px)
    e = np.hypot(ry - iy, rx - ix)
    return {
        "n_reference_points_scored": int(rz.size),
        "n_picked": len(picked),
        "median": float(np.median(e)),
        "p90": float(np.percentile(e, 90)),
        "max": float(e.max()),
        "mean": float(e.mean()),
        "per_point": [
            {"z": int(a), "error": float(b)} for a, b in zip(rz, e)
        ],
    }


def self_consistency(points: list[dict]) -> dict:
    """The reference's own noise: each interior point vs its neighbours' chord."""
    z, y, x = curve(points)
    dev = []
    for i in range(1, len(z) - 1):
        span = z[i + 1] - z[i - 1]
        if span <= 0:
            continue
        t = (z[i] - z[i - 1]) / span
        dev.append(
            np.hypot(
                y[i] - (y[i - 1] + t * (y[i + 1] - y[i - 1])),
                x[i] - (x[i - 1] + t * (x[i + 1] - x[i - 1])),
            )
        )
    dev = np.array(dev)
    return {"median": float(np.median(dev)), "p90": float(np.percentile(dev, 90)), "max": float(dev.max())}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("scroll")
    ap.add_argument("--reference", default=None)
    args = ap.parse_args()

    ref_path = args.reference or f"reference/{args.scroll}_umbilicus.json"
    reference = json.load(open(ref_path))["control_points"]
    picked = load_picked(args.scroll)

    res = compare(picked, reference)
    sc = self_consistency(reference)

    print(f"{args.scroll}: {res['n_picked']} picked points vs "
          f"{res['n_reference_points_scored']} reference points")
    print(f"  agreement  median {res['median']:7.1f}   p90 {res['p90']:7.1f}   max {res['max']:7.1f}")
    print(f"  reference's own noise:")
    print(f"             median {sc['median']:7.1f}   p90 {sc['p90']:7.1f}   max {sc['max']:7.1f}")
    verdict = "PASS" if res["median"] <= sc["median"] else "MISS"
    print(f"  frozen target: median <= reference median  ->  {verdict}")
    print()
    worst = sorted(res["per_point"], key=lambda d: -d["error"])[:6]
    print("  worst z: " + ", ".join(f"z={d['z']}:{d['error']:.0f}" for d in worst))
