"""Draw a reference curve and/or picked points onto an existing montage.

Used for two things: calibrating the picking judgement against a known-good
curve, and producing the per-scroll verification figures that ship with the
release so a reader can check every control point by eye.
"""

from __future__ import annotations

import argparse
import glob
import json
import os

import numpy as np
from PIL import Image, ImageDraw

from montage import picks_to_points


def _interp_at(points, z):
    pz = np.array([p["z"] for p in points], float)
    o = np.argsort(pz)
    pz = pz[o]
    py = np.array([p["y"] for p in points], float)[o]
    px = np.array([p["x"] for p in points], float)[o]
    return float(np.interp(z, pz, py)), float(np.interp(z, pz, px))


def _to_panel(panel, y_full, x_full):
    vpp = panel["voxels_per_px"]
    px = (x_full - panel["x0_full"]) / vpp
    py = (y_full - panel["y0_full"]) / vpp
    return panel["origin_px"][0] + px, panel["origin_px"][1] + py


def annotate(manifest_path: str, out_png: str, *, reference=None, picked=None) -> None:
    m = json.load(open(manifest_path))
    src = os.path.join(os.path.dirname(manifest_path), m["png"])
    img = Image.open(src).convert("RGB")
    d = ImageDraw.Draw(img)

    for panel in m["panels"]:
        if panel.get("empty"):
            continue
        z = panel["z"]
        if reference:
            ry, rx = _interp_at(reference, z)
            cx, cy = _to_panel(panel, ry, rx)
            r = 11
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(0, 255, 255), width=3)
            d.line([(cx - r - 6, cy), (cx - r, cy)], fill=(0, 255, 255), width=3)
            d.line([(cx + r, cy), (cx + r + 6, cy)], fill=(0, 255, 255), width=3)
        if picked:
            py_, px_ = _interp_at(picked, z)
            cx, cy = _to_panel(panel, py_, px_)
            r = 7
            d.line([(cx - r, cy - r), (cx + r, cy + r)], fill=(255, 60, 60), width=3)
            d.line([(cx - r, cy + r), (cx + r, cy - r)], fill=(255, 60, 60), width=3)
    img.save(out_png)


def load_picked(scroll: str, picks_dir: str = "picks"):
    pts = []
    for pf in sorted(glob.glob(os.path.join(picks_dir, f"{scroll}_p*.json"))):
        rec = json.load(open(pf))
        manifest = json.load(open(rec["manifest"]))
        picks = {int(k): tuple(v) for k, v in rec["picks"].items()}
        pts.extend(picks_to_points(manifest, picks))
    return sorted(pts, key=lambda p: p["z"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("out")
    ap.add_argument("--scroll", default=None, help="draw this scroll's recorded picks")
    ap.add_argument("--reference", default=None, help="path to a reference umbilicus.json")
    args = ap.parse_args()

    ref = json.load(open(args.reference))["control_points"] if args.reference else None
    pick = load_picked(args.scroll) if args.scroll else None
    annotate(args.manifest, args.out, reference=ref, picked=pick)
    print("wrote", args.out)
