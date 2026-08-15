"""Per-scroll deformation index, and what it implies for seed quality.

The seed curve is the centroid of the scroll body, so it approximates the
umbilicus exactly to the extent that the cross-section is round and concentric.
Measured against the four public references the seed error ranges from 46.5 voxels
(PHerc1218) to 381.7 (PHerc0826) — an eightfold spread that is not noise but a
property of how badly each scroll is crushed.

Quantifying that up front is useful triage: it says which scrolls the centroid
nearly solves and which need the most manual attention, before any time is spent.

`solidity` is mask area over convex-hull area: 1.0 for a convex (round) section,
lower as the body folds in on itself.  `elongation` is the ratio of the principal
axes of the mask.  Both are averaged over evenly spaced z.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage


def slice_shape_stats(reader, z0: int, level: int = 5, intensity_min: int = 40) -> dict | None:
    scale = reader.pyr.scale(level)
    sz = reader.pyr.shapes[level][0]
    zl = max(0, min(sz - 1, int(round(z0 / scale))))
    img = reader.read_full_slice(level, zl)
    mask = img > intensity_min
    if mask.sum() < 64:
        return None
    lab, n = ndimage.label(mask)
    if n > 1:
        sizes = ndimage.sum(mask, lab, range(1, n + 1))
        mask = lab == (int(np.argmax(sizes)) + 1)

    area = float(mask.sum())
    ys, xs = np.nonzero(mask)

    # principal axes from the second moments of the mask
    cy, cx = ys.mean(), xs.mean()
    cov = np.cov(np.stack([ys - cy, xs - cx]))
    ev = np.sort(np.linalg.eigvalsh(cov))[::-1]
    elongation = float(np.sqrt(ev[0] / max(ev[1], 1e-9)))

    try:
        from skimage.morphology import convex_hull_image

        hull = convex_hull_image(mask)
        solidity = float(area / max(hull.sum(), 1))
    except Exception:
        solidity = float("nan")

    return {"area": area, "elongation": elongation, "solidity": solidity}


def scroll_deformation(reader, z_lo: int, z_hi: int, n: int = 12, level: int = 5) -> dict:
    zs = np.linspace(z_lo + 0.05 * (z_hi - z_lo), z_hi - 0.05 * (z_hi - z_lo), n)
    el, so = [], []
    for z in zs:
        s = slice_shape_stats(reader, int(z), level=level)
        if s is None:
            continue
        el.append(s["elongation"])
        so.append(s["solidity"])
    if not el:
        raise ValueError("no usable slices")
    return {
        "elongation_median": float(np.median(el)),
        "solidity_median": float(np.nanmedian(so)),
        "n_slices": len(el),
    }
