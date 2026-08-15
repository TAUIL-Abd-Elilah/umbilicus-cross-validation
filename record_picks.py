"""Append a batch of panel-pixel picks to a scroll's running sequential track.

    python record_picks.py PHerc0826 --batch 0 --picks "0:255,258 1:288,308 2:272,307"

Panel coordinates are (px, py) as drawn on the montage grid.  The manifest written
by `sequential_pick.py` carries the geometry, so a pick is reproducible from the
recorded pixel pair alone.  Omitting a panel index skips that z, which is the right
move when a slice is genuinely unreadable rather than guessing at it.
"""

import argparse
import json
import os

ap = argparse.ArgumentParser()
ap.add_argument("scroll")
ap.add_argument("--batch", type=int, required=True)
ap.add_argument("--picks", required=True, help='e.g. "0:255,258 1:288,308"')
ap.add_argument("--confidence", default="", help='e.g. "0:low 1:high"')
args = ap.parse_args()

man = json.load(open(f"picking/{args.scroll}_seq{args.batch}.json"))
by_index = {p["index"]: p for p in man["panels"]}

conf = {}
for tok in args.confidence.split():
    i, c = tok.split(":")
    conf[int(i)] = c

new = []
for tok in args.picks.split():
    idx, xy = tok.split(":")
    px, py = (float(v) for v in xy.split(","))
    p = by_index[int(idx)]
    vpp = p["voxels_per_px"]
    new.append(
        {
            "z": p["z"],
            "y": int(round(p["y0_full"] + py * vpp)),
            "x": int(round(p["x0_full"] + px * vpp)),
            "score": 100,
            "batch": args.batch,
            "panel_px": [px, py],
            "confidence": conf.get(int(idx), "medium"),
        }
    )

path = f"picks/{args.scroll}_seq.json"
os.makedirs("picks", exist_ok=True)
doc = json.load(open(path)) if os.path.exists(path) else {"scroll": args.scroll, "points": []}
doc["points"] = [p for p in doc["points"] if p["z"] not in {q["z"] for q in new}] + new
doc["points"].sort(key=lambda p: p["z"])
json.dump(doc, open(path, "w"), indent=1)

for p in new:
    print(f"  z={p['z']:6d} -> y={p['y']:5d} x={p['x']:5d}  ({p['confidence']})")
print(f"track now has {len(doc['points'])} points -> {path}")
