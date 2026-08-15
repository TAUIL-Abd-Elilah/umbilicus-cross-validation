"""Estimate the umbilicus of a scroll z-slice by radial alignment of sheet normals.

Mechanism
---------
Papyrus sheets wind around the umbilicus, so at a point `p` on a sheet the sheet
*normal* points roughly along the radius from the umbilicus to `p`.  Writing the
unit normal at `p` as `n(p)` and the unit radius from a candidate centre `u` as
`r(p; u) = (p - u) / |p - u|`, the true umbilicus is the `u` that maximises

    S(u) = sum_p  w(p) * <n(p), r(p; u)>^2                                   (1)

over sheet pixels `p` in an annulus around `u`.  The square removes the sign
ambiguity of an eigenvector-derived normal; `w(p)` is the structure-tensor
coherence, so well-formed lamellae dominate and noise/void contributes little.

This is a *different mechanism* from a normal-field centreline optimiser that
walks a curve under a smoothness prior: (1) is a bounded, dense, per-slice
score with no temporal state, evaluated by exhaustive grid search rather than
gradient descent, so it cannot walk off into a local minimum and drag the rest
of the curve with it.  Each slice is independent; the only coupling across z is
the search window, which is centred on an interpolated anchor.

The annulus matters.  As `|p - u| -> inf` every `r(p; u)` becomes parallel and
locally-parallel lamellae score highly for a centre placed arbitrarily far away,
so (1) has a degenerate far field.  `r_inner`/`r_outer` bound the evaluation to
the region where the winding actually curves around the centre.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage


@dataclass
class EstimatorConfig:
    """All lengths are in FULL-RESOLUTION voxels; the code converts to level px."""

    level: int = 2
    window: int = 2048           # side of the analysed window, full-res voxels
    search_radius: int = 512     # max distance the estimate may move from anchor
    search_step: int = 16        # grid resolution of the centre search, full-res
    r_inner: int = 120           # annulus inner radius
    r_outer: int = 900           # annulus outer radius
    smooth_sigma: float = 1.5    # gradient scale, level px
    tensor_sigma: float = 4.0    # structure-tensor integration scale, level px
    coherence_min: float = 0.25  # discard poorly oriented pixels
    intensity_min: int = 40      # discard air/void
    max_samples: int = 20000     # subsample sheet pixels for speed


def structure_tensor_normals(
    img: np.ndarray, cfg: EstimatorConfig
) -> tuple[np.ndarray, np.ndarray]:
    """Return (normal_yx, coherence) for every pixel of `img`.

    The normal is the principal eigenvector of the structure tensor, i.e. the
    direction of greatest intensity change, which is perpendicular to the sheet.
    """
    f = img.astype(np.float32)
    gy = ndimage.gaussian_filter(f, cfg.smooth_sigma, order=(1, 0))
    gx = ndimage.gaussian_filter(f, cfg.smooth_sigma, order=(0, 1))

    jyy = ndimage.gaussian_filter(gy * gy, cfg.tensor_sigma)
    jxx = ndimage.gaussian_filter(gx * gx, cfg.tensor_sigma)
    jyx = ndimage.gaussian_filter(gy * gx, cfg.tensor_sigma)

    # closed-form eigen-decomposition of the symmetric 2x2 tensor
    tr = jyy + jxx
    diff = jyy - jxx
    disc = np.sqrt(np.maximum(diff * diff + 4.0 * jyx * jyx, 0.0))
    lam1 = 0.5 * (tr + disc)          # larger eigenvalue
    lam2 = 0.5 * (tr - disc)

    # eigenvector for lam1
    ny = jyx
    nx = lam1 - jyy
    norm = np.hypot(ny, nx)
    flat = norm < 1e-12
    ny = np.where(flat, 1.0, ny / np.where(flat, 1.0, norm))
    nx = np.where(flat, 0.0, nx / np.where(flat, 1.0, norm))

    coherence = np.where(tr > 1e-12, (lam1 - lam2) / np.maximum(tr, 1e-12), 0.0)
    return np.stack([ny, nx], axis=-1), coherence.astype(np.float32)


def score_grid(
    pts_yx: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    cand_y: np.ndarray,
    cand_x: np.ndarray,
    r_inner: float,
    r_outer: float,
) -> np.ndarray:
    """Evaluate S(u) of the module docstring for every candidate centre.

    Returns an array of shape (len(cand_y), len(cand_x)).
    """
    out = np.zeros((cand_y.size, cand_x.size), dtype=np.float64)
    py, px = pts_yx[:, 0], pts_yx[:, 1]
    ny, nx = normals[:, 0], normals[:, 1]
    r2_in, r2_out = r_inner * r_inner, r_outer * r_outer
    for i, cy in enumerate(cand_y):
        dy = py - cy
        dy2 = dy * dy
        for j, cx in enumerate(cand_x):
            dx = px - cx
            r2 = dy2 + dx * dx
            m = (r2 > r2_in) & (r2 < r2_out)
            if not m.any():
                continue
            inv = 1.0 / np.sqrt(r2[m])
            dot = (ny[m] * dy[m] + nx[m] * dx[m]) * inv
            out[i, j] = np.dot(weights[m], dot * dot)
    return out


def estimate_slice(
    reader,
    z0: int,
    anchor_yx: tuple[float, float],
    cfg: EstimatorConfig,
) -> dict:
    """Estimate the umbilicus on one z-slice.

    `z0` and `anchor_yx` are in full-resolution voxels.  Returns a dict with the
    refined centre, the peak score, and a sharpness diagnostic that says how
    well-determined the peak is.
    """
    scale = reader.pyr.scale(cfg.level)
    zl = int(round(z0 / scale))
    zl = max(0, min(reader.pyr.shapes[cfg.level][0] - 1, zl))

    ay, ax = anchor_yx
    half = cfg.window // 2
    y0, x0 = int(round((ay - half) / scale)), int(round((ax - half) / scale))
    n = int(round(cfg.window / scale))
    img = reader.read_window(cfg.level, zl, y0, y0 + n, x0, x0 + n)

    normals, coherence = structure_tensor_normals(img, cfg)
    keep = (coherence > cfg.coherence_min) & (img > cfg.intensity_min)
    idx = np.flatnonzero(keep.ravel())
    if idx.size < 200:
        return {"ok": False, "reason": "too few oriented sheet pixels", "n_pixels": int(idx.size)}
    if idx.size > cfg.max_samples:
        rng = np.random.default_rng(0)          # deterministic subsample
        idx = rng.choice(idx, cfg.max_samples, replace=False)

    yy, xx = np.unravel_index(idx, img.shape)
    pts = np.stack([yy, xx], axis=-1).astype(np.float32) * scale       # -> full-res
    pts[:, 0] += y0 * scale
    pts[:, 1] += x0 * scale
    nrm = normals.reshape(-1, 2)[idx]
    wts = coherence.ravel()[idx].astype(np.float64)

    step = cfg.search_step
    rad = cfg.search_radius
    cand_y = np.arange(ay - rad, ay + rad + 1, step, dtype=np.float64)
    cand_x = np.arange(ax - rad, ax + rad + 1, step, dtype=np.float64)
    grid = score_grid(pts, nrm, wts, cand_y, cand_x, cfg.r_inner, cfg.r_outer)

    if not np.isfinite(grid).any() or grid.max() <= 0:
        return {"ok": False, "reason": "degenerate score grid", "n_pixels": int(idx.size)}

    bi, bj = np.unravel_index(np.argmax(grid), grid.shape)
    best = grid[bi, bj]

    # sub-grid refinement by a local intensity-weighted centroid of the top ridge
    lo = best * 0.995
    my, mx = np.where(grid >= lo)
    wsub = grid[my, mx] - lo
    if wsub.sum() > 0:
        ry = float((cand_y[my] * wsub).sum() / wsub.sum())
        rx = float((cand_x[mx] * wsub).sum() / wsub.sum())
    else:
        ry, rx = float(cand_y[bi]), float(cand_x[bj])

    # how peaked is the maximum?  a flat grid means the slice does not constrain u
    med = float(np.median(grid))
    sharpness = float((best - med) / best) if best > 0 else 0.0
    spread = float(np.hypot(cand_y[my].std(), cand_x[mx].std())) if my.size > 1 else 0.0

    return {
        "ok": True,
        "z": int(z0),
        "y": ry,
        "x": rx,
        "score": float(best),
        "sharpness": sharpness,
        "ridge_spread": spread,
        "n_pixels": int(idx.size),
        "moved": float(np.hypot(ry - ay, rx - ax)),
    }
