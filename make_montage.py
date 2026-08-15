"""Build a picking montage for one scroll.

    python make_montage.py PHerc0211 --n 16 --part 0

`--part` selects which subset of the z schedule to render when a scroll needs more
control points than fit legibly in one image: part 0 renders the even-indexed z
of a 2*n schedule, part 1 the odd-indexed ones, so the two montages interleave
into a single evenly-spaced curve.
"""

import argparse
import json
import os
import time

from coarse_center import z_span
from montage import build_montage, plan_zs
from scrolls import SCROLLS
from slicefetch import SliceReader, open_pyramid, scroll_volume_path

ap = argparse.ArgumentParser()
ap.add_argument("scroll")
ap.add_argument("--n", type=int, default=16, help="panels in this montage")
ap.add_argument("--part", type=int, default=0, help="0-based; interleaved subsets")
ap.add_argument("--parts", type=int, default=2, help="total interleaved parts")
ap.add_argument("--window", type=int, default=4096)
ap.add_argument("--level", type=int, default=3)
ap.add_argument("--panel-px", type=int, default=384)
ap.add_argument("--outdir", default="picking")
args = ap.parse_args()

meta = SCROLLS[args.scroll]
pyr = open_pyramid(scroll_volume_path(args.scroll, meta["ct"]))
reader = SliceReader(pyr, cache_dir="cache")

os.makedirs(args.outdir, exist_ok=True)
span_path = os.path.join(args.outdir, f"{args.scroll}_span.json")
if os.path.exists(span_path):
    lo, hi = json.load(open(span_path))
else:
    t = time.time()
    lo, hi = z_span(reader)
    json.dump([lo, hi], open(span_path, "w"))
    print(f"z span {lo}-{hi} (probed in {time.time() - t:.0f}s)")

total = args.n * args.parts
zs_all = plan_zs(lo, hi, total)
zs = zs_all[args.part :: args.parts]

t = time.time()
m = build_montage(
    reader,
    args.scroll,
    zs,
    out_png=os.path.join(args.outdir, f"{args.scroll}_p{args.part}.png"),
    out_manifest=os.path.join(args.outdir, f"{args.scroll}_p{args.part}.json"),
    level=args.level,
    window=args.window,
    panel_px=args.panel_px,
)
print(
    f"{args.scroll} part {args.part}: {len(zs)} panels, z {zs[0]}..{zs[-1]}, "
    f"{reader.bytes_fetched / 1e6:.1f} MB, {time.time() - t:.0f}s"
)
print(f"  {m['window_full'] / m['panel_px']:.1f} full-res voxels per panel pixel")
