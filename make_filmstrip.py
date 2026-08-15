"""Build a tracking filmstrip for one scroll, anchored on its seed curve.

    python make_filmstrip.py PHerc0211 --n 24
    python make_filmstrip.py PHerc0211 --n 24 --anchor picks/PHerc0211_track.json
"""

import argparse
import json
import os

from filmstrip import build_filmstrip, seed_interpolator
from montage import plan_zs
from scrolls import SCROLLS
from slicefetch import SliceReader, open_pyramid, scroll_volume_path

ap = argparse.ArgumentParser()
ap.add_argument("scroll")
ap.add_argument("--n", type=int, default=24)
ap.add_argument("--window", type=int, default=2048)
ap.add_argument("--level", type=int, default=2)
ap.add_argument("--panel-px", type=int, default=256)
ap.add_argument("--cols", type=int, default=6)
ap.add_argument("--anchor", default=None, help="umbilicus json to anchor on (default: seed)")
ap.add_argument("--tag", default="f0")
ap.add_argument("--outdir", default="picking")
args = ap.parse_args()

meta = SCROLLS[args.scroll]
pyr = open_pyramid(scroll_volume_path(args.scroll, meta["ct"]))
reader = SliceReader(pyr, cache_dir="cache")

anchor_path = args.anchor or f"seeds/{args.scroll}_umbilicus_seed.json"
anchor_pts = json.load(open(anchor_path))["control_points"]
anchor_of_z = seed_interpolator(anchor_pts)

lo, hi = json.load(open(f"seeds/index.json"))[args.scroll]["z_span"]
zs = plan_zs(lo, hi, args.n)

os.makedirs(args.outdir, exist_ok=True)
m = build_filmstrip(
    reader,
    args.scroll,
    zs,
    anchor_of_z,
    out_png=os.path.join(args.outdir, f"{args.scroll}_{args.tag}.png"),
    out_manifest=os.path.join(args.outdir, f"{args.scroll}_{args.tag}.json"),
    level=args.level,
    window=args.window,
    panel_px=args.panel_px,
    cols=args.cols,
)
print(f"{args.scroll} {args.tag}: {len(zs)} panels, z {zs[0]}..{zs[-1]}, "
      f"anchor={os.path.basename(anchor_path)}, {reader.bytes_fetched/1e6:.1f} MB")
print(f"  {m['window_full']/m['panel_px']:.1f} full-res voxels per panel pixel, "
      f"dz={zs[1]-zs[0]}")
