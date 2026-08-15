"""Does radial-normal convergence work when fed the *trained* normal field?

Same score as `umbilicus_estimator.score_grid` — the umbilicus is where the sheet
normals converge — but the normals come from the published lasagna prediction
instead of a structure tensor on raw CT.  The earlier failure may have been the
input rather than the criterion.

Baseline to beat: the body-centroid seed, at 289-382 voxels median.
"""

import json
import sys

import numpy as np

from coarse_center import body_centroid
from lasagna import LasagnaNormals
from scrolls import SCROLLS
from slicefetch import SliceReader, open_pyramid, scroll_volume_path
from umbilicus_estimator import score_grid

WINDOW = 4096          # full-res voxels analysed around the seed
SEARCH = 700           # how far the estimate may move from the seed
STEP = 16
R_INNER, R_OUTER = 150, 1400

scroll = sys.argv[1] if len(sys.argv) > 1 else "PHerc0211"
n_z = int(sys.argv[2]) if len(sys.argv) > 2 else 8

ref = sorted(
    json.load(open(f"reference/{scroll}_umbilicus.json"))["control_points"],
    key=lambda p: p["z"],
)
rz = np.array([p["z"] for p in ref], float)
ry = np.array([p["y"] for p in ref], float)
rx = np.array([p["x"] for p in ref], float)

pyr = open_pyramid(scroll_volume_path(scroll, SCROLLS[scroll]["ct"]))
reader = SliceReader(pyr, cache_dir="cache")
las = LasagnaNormals(scroll, level=4)
scale = las.scale
print(f"{scroll}: lasagna L4 shape {las.shape}, scale {scale}")

seed_err, las_err = [], []
print("%8s %10s %10s %8s" % ("z", "seed err", "lasagna", "weight"))
for z in np.linspace(rz[2], rz[-3], n_z):
    z = int(z)
    c = body_centroid(reader, z)
    if c is None:
        continue
    cy, cx = c
    ty, tx = float(np.interp(z, rz, ry)), float(np.interp(z, rz, rx))

    zl = max(0, min(las.shape[0] - 1, int(round(z / scale))))
    n = WINDOW // scale
    y0 = int(round((cy - WINDOW / 2) / scale))
    x0 = int(round((cx - WINDOW / 2) / scale))
    normals, weight = las.read(zl, y0, y0 + n, x0, x0 + n)

    keep = weight > 0.05
    idx = np.flatnonzero(keep.ravel())
    if idx.size < 500:
        print("%8d  (too few confident normals: %d)" % (z, idx.size))
        continue
    if idx.size > 30000:
        idx = np.random.default_rng(0).choice(idx, 30000, replace=False)
    yy, xx = np.unravel_index(idx, weight.shape)
    pts = np.stack([(y0 + yy) * scale, (x0 + xx) * scale], axis=-1).astype(np.float64)
    nrm = normals.reshape(-1, 2)[idx].astype(np.float64)
    wts = weight.ravel()[idx].astype(np.float64)

    cand_y = np.arange(cy - SEARCH, cy + SEARCH + 1, STEP, dtype=np.float64)
    cand_x = np.arange(cx - SEARCH, cx + SEARCH + 1, STEP, dtype=np.float64)
    grid = score_grid(pts, nrm, wts, cand_y, cand_x, R_INNER, R_OUTER)
    bi, bj = np.unravel_index(int(np.argmax(grid)), grid.shape)
    gy, gx = float(cand_y[bi]), float(cand_x[bj])

    se = float(np.hypot(cy - ty, cx - tx))
    le = float(np.hypot(gy - ty, gx - tx))
    seed_err.append(se)
    las_err.append(le)
    print("%8d %10.1f %10.1f %8.3f" % (z, se, le, float(wts.mean())))

if seed_err:
    s, l = np.array(seed_err), np.array(las_err)
    print()
    print("seed    median %7.1f   p90 %7.1f" % (np.median(s), np.percentile(s, 90)))
    print("lasagna median %7.1f   p90 %7.1f" % (np.median(l), np.percentile(l, 90)))
    print("fetched %.1f MB" % (las.bytes_fetched / 1e6))
