"""End-to-end umbilicus estimation: lasagna normals + continuity, by DP.

    python estimate_umbilicus.py PHerc0211 --n 40
    python estimate_umbilicus.py PHerc0800 --n 40 --out seeds/PHerc0800_est.json

Per z, the score is the radial convergence of the published lasagna sheet normals
on a candidate grid centred on the body-centroid seed.  The stack of score grids is
then resolved into one smooth track by `track.viterbi_track`.
"""

import argparse
import json
import os
import time

import numpy as np

from coarse_center import body_centroid
from lasagna import LasagnaNormals
from montage import write_umbilicus
from scrolls import SCROLLS
from seed_curve import build_seed
from slicefetch import SliceReader, open_pyramid, scroll_volume_path
from track import viterbi_track
from umbilicus_estimator import score_grid

ap = argparse.ArgumentParser()
ap.add_argument("scroll")
ap.add_argument("--n", type=int, default=40, help="z samples")
ap.add_argument("--window", type=int, default=4096)
ap.add_argument("--search", type=int, default=700)
ap.add_argument("--step", type=int, default=24)
ap.add_argument("--r-inner", type=int, default=150)
ap.add_argument("--r-outer", type=int, default=1400)
ap.add_argument("--lam", type=float, default=0.0)  # measured best; see PROTOCOL.md Amendment 05
ap.add_argument("--max-step-per-z", type=float, default=2.0)
ap.add_argument("--level", type=int, default=4)
ap.add_argument("--max-points", type=int, default=15000)
ap.add_argument("--out", default=None)
ap.add_argument("--save-grids", default=None, help="npz cache of the score grids")
args = ap.parse_args()

meta = SCROLLS[args.scroll]
pyr = open_pyramid(scroll_volume_path(args.scroll, meta["ct"]))
reader = SliceReader(pyr, cache_dir="cache")
las = LasagnaNormals(args.scroll, level=args.level)
scale = las.scale

span_path = "seeds/index.json"
lo, hi = json.load(open(span_path))[args.scroll]["z_span"]
zs = [int(v) for v in np.linspace(lo + 0.03 * (hi - lo), hi - 0.03 * (hi - lo), args.n)]

# a single common candidate grid, anchored on the mean seed position, so the DP
# compares like with like across z
seed = build_seed(reader, lo, hi, n_points=max(16, args.n // 2))
sz = np.array([p["z"] for p in seed], float)
sy = np.array([p["y"] for p in seed], float)
sx = np.array([p["x"] for p in seed], float)

t0 = time.time()
grids, kept_z, anchors = [], [], []
for z in zs:
    ay = float(np.interp(z, sz, sy))
    ax = float(np.interp(z, sz, sx))
    zl = max(0, min(las.shape[0] - 1, int(round(z / scale))))
    n = args.window // scale
    y0 = int(round((ay - args.window / 2) / scale))
    x0 = int(round((ax - args.window / 2) / scale))
    normals, weight = las.read(zl, y0, y0 + n, x0, x0 + n)

    idx = np.flatnonzero(weight.ravel() > 0.05)
    if idx.size < 500:
        continue
    if idx.size > args.max_points:
        idx = np.random.default_rng(0).choice(idx, args.max_points, replace=False)
    yy, xx = np.unravel_index(idx, weight.shape)
    pts = np.stack([(y0 + yy) * scale, (x0 + xx) * scale], axis=-1).astype(np.float64)
    nrm = normals.reshape(-1, 2)[idx].astype(np.float64)
    wts = weight.ravel()[idx].astype(np.float64)

    cy = np.arange(ay - args.search, ay + args.search + 1, args.step, dtype=np.float64)
    cx = np.arange(ax - args.search, ax + args.search + 1, args.step, dtype=np.float64)
    # express the grid in offsets from the anchor so all slices share one frame
    g = score_grid(pts, nrm, wts, cy, cx, args.r_inner, args.r_outer)
    grids.append(g)
    kept_z.append(float(z))
    anchors.append((ay, ax))

if args.save_grids:
    np.savez_compressed(
        args.save_grids,
        grids=np.stack(grids),
        zs=np.array(kept_z),
        anchors=np.array(anchors),
        search=args.search,
        step=args.step,
    )
    print(f"  cached {len(grids)} score grids -> {args.save_grids}")

off = np.arange(-args.search, args.search + 1, args.step, dtype=np.float64)
ty, tx, info = viterbi_track(
    grids, kept_z, off, off, lam=args.lam, max_step_per_z=args.max_step_per_z
)
ty = ty + np.array([a[0] for a in anchors])
tx = tx + np.array([a[1] for a in anchors])

points = [
    {"x": int(round(x)), "y": int(round(y)), "z": int(z), "score": 100}
    for z, y, x in zip(kept_z, ty, tx)
]
out = args.out or f"seeds/{args.scroll}_umbilicus_estimated.json"
os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
write_umbilicus(
    points,
    out,
    note=(
        "Automatic estimate: lasagna sheet-normal radial convergence per z, "
        "resolved into one track by dynamic programming with a continuity prior. "
        "Not manually verified."
    ),
)
print(f"{args.scroll}: {len(points)} points, {time.time()-t0:.0f}s, "
      f"{las.bytes_fetched/1e6:.0f} MB -> {out}")
print("  median per-slice score kept vs that slice's best: "
      f"{np.median(info['score_ratio']):.3f}")
