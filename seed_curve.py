"""Produce an automatic *seed* umbilicus for a scroll.

This is deliberately not presented as a finished umbilicus.  Two independent
attempts to locate the umbilicus without a human failed on real prize scrolls
(PROTOCOL.md), and the reason is structural: on a crushed scroll the umbilicus is
a topological property of the winding, not a local feature of any one slice.

What *is* reliable is the scroll body itself.  The centroid of the cross-section
sits a measured 269-394 voxels (median) from the true umbilicus, which is far too
coarse to publish but is a good starting curve for an annotator: it puts every
control point in roughly the right place, at roughly the right z, in the right
file format, so the manual pass becomes correction rather than creation.

Smoothing in z was tried and is **off by default because it measurably hurts**.
Against the three reference curves the raw centroid scores a median of 292 / 292 /
356 voxels, and the smoothed version 310 / 437 / 477.  The centroid's jitter is
apparently correlated with genuine motion of the body rather than being additive
noise, so averaging it drags the curve off the umbilicus.  `smooth=True` is kept
so the comparison can be rerun.
"""

from __future__ import annotations

import numpy as np

from coarse_center import body_centroid


def robust_smooth(z: np.ndarray, v: np.ndarray, window: int = 7, passes: int = 2) -> np.ndarray:
    """Median filter then moving average, both odd-windowed and edge-preserving.

    The median pass removes single-slice centroid outliers (a detached fragment
    entering the mask); the mean pass takes out the residual jitter.
    """
    out = v.astype(float).copy()
    half = window // 2
    for _ in range(passes):
        med = out.copy()
        for i in range(len(out)):
            lo, hi = max(0, i - half), min(len(out), i + half + 1)
            med[i] = np.median(out[lo:hi])
        avg = med.copy()
        for i in range(len(med)):
            lo, hi = max(0, i - half), min(len(med), i + half + 1)
            avg[i] = med[lo:hi].mean()
        out = avg
    return out


def build_seed(
    reader,
    z_lo: int,
    z_hi: int,
    n_points: int = 32,
    level: int = 5,
    margin: float = 0.02,
    smooth: bool = False,
) -> list[dict]:
    """Sample body centroids across [z_lo, z_hi] and return seed control points."""
    span = z_hi - z_lo
    zs = np.linspace(z_lo + margin * span, z_hi - margin * span, n_points)
    zs = [int(round(v)) for v in zs]

    got_z, got_y, got_x = [], [], []
    for z in zs:
        c = body_centroid(reader, z, level=level)
        if c is None:
            continue
        got_z.append(z)
        got_y.append(c[0])
        got_x.append(c[1])
    if len(got_z) < 3:
        raise ValueError("scroll body found on fewer than 3 probed slices")

    z = np.array(got_z, float)
    y = np.array(got_y, float)
    x = np.array(got_x, float)
    if smooth and len(z) >= 5:
        y = robust_smooth(z, y)
        x = robust_smooth(z, x)

    return [
        {"x": int(round(xx)), "y": int(round(yy)), "z": int(zz), "score": 50}
        for zz, yy, xx in zip(z, y, x)
    ]
