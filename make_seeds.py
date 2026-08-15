"""Generate seed umbilicus curves for every eligible scroll.

    python make_seeds.py            # all 13
    python make_seeds.py PHerc0800  # one

Writes `seeds/<scroll>_umbilicus_seed.json` in the standard schema, plus a
`seeds/index.json` recording the z span and how each seed was produced.  Resumable:
a scroll that already has a seed is skipped.
"""

import json
import os
import sys
import time

from coarse_center import z_span
from montage import write_umbilicus
from scrolls import SCROLLS
from seed_curve import build_seed
from slicefetch import SliceReader, open_pyramid, scroll_volume_path

OUT = "seeds"
os.makedirs(OUT, exist_ok=True)
targets = sys.argv[1:] or list(SCROLLS)

index_path = os.path.join(OUT, "index.json")
index = json.load(open(index_path)) if os.path.exists(index_path) else {}

for name in targets:
    out_path = os.path.join(OUT, f"{name}_umbilicus_seed.json")
    if os.path.exists(out_path):
        print(f"{name}: already present, skipping")
        continue
    meta = SCROLLS[name]
    t = time.time()
    try:
        pyr = open_pyramid(scroll_volume_path(name, meta["ct"]))
        reader = SliceReader(pyr, cache_dir="cache")
        lo, hi = z_span(reader)
        pts = build_seed(reader, lo, hi, n_points=32)
        write_umbilicus(
            pts,
            out_path,
            note=(
                "AUTOMATIC SEED, NOT A FINISHED UMBILICUS. Body-centroid initialisation; "
                "measured median error against public reference curves is ~300 voxels. "
                "Intended as a starting curve for manual correction in khartes."
            ),
        )
        index[name] = {
            "ct": meta["ct"],
            "z_span": [lo, hi],
            "n_points": len(pts),
            "method": "body centroid at level 5, unsmoothed",
            "seconds": round(time.time() - t, 1),
        }
        json.dump(index, open(index_path, "w"), indent=1)
        print(f"{name}: {len(pts)} pts, z {lo}-{hi}, {time.time() - t:.0f}s")
    except Exception as e:
        print(f"{name}: FAILED {type(e).__name__}: {e}")
