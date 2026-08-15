"""Cheap per-z window centring from the scroll body itself.

The visual picking step needs each montage panel to *contain* the umbilicus, not
to be centred on it.  The centroid of the masked scroll cross-section is a good
enough anchor for that: it is free to compute at a coarse pyramid level, and the
umbilicus of a rolled scroll stays well inside the body.

`body_centroid` returns full-resolution voxel coordinates so it can be dropped
straight into the same coordinate frame as the control points.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage


def body_centroid(reader, z0: int, level: int = 5, intensity_min: int = 40) -> tuple[float, float] | None:
    """Centroid of the largest connected bright component of one z-slice.

    Returns (y, x) in full-resolution voxels, or None if the slice is empty.
    """
    scale = reader.pyr.scale(level)
    sz = reader.pyr.shapes[level][0]
    zl = max(0, min(sz - 1, int(round(z0 / scale))))
    img = reader.read_full_slice(level, zl)

    mask = img > intensity_min
    if mask.sum() < 16:
        return None
    # the scan can contain detached debris; keep only the main body
    lab, n = ndimage.label(mask)
    if n > 1:
        sizes = ndimage.sum(mask, lab, range(1, n + 1))
        mask = lab == (int(np.argmax(sizes)) + 1)
    cy, cx = ndimage.center_of_mass(mask)
    return float(cy * scale), float(cx * scale)


def body_extent(reader, z0: int, level: int = 5, intensity_min: int = 40) -> float | None:
    """Rough diameter of the body at `z0`, in full-resolution voxels."""
    scale = reader.pyr.scale(level)
    sz = reader.pyr.shapes[level][0]
    zl = max(0, min(sz - 1, int(round(z0 / scale))))
    img = reader.read_full_slice(level, zl)
    mask = img > intensity_min
    if mask.sum() < 16:
        return None
    ys, xs = np.nonzero(mask)
    return float(max(ys.ptp(), xs.ptp()) * scale)


def z_span(reader, level: int = 5, intensity_min: int = 40, probe: int = 40) -> tuple[int, int]:
    """Find the first and last z (full-res) where the scroll body is present.

    Scans `probe` evenly spaced slices at a coarse level; the scroll occupies a
    contiguous run of z, so the first and last occupied probe bracket the body.
    """
    scale = reader.pyr.scale(level)
    sz = reader.pyr.shapes[level][0]
    zs = np.linspace(0, sz - 1, probe).round().astype(int)
    occupied = []
    for zl in zs:
        img = reader.read_full_slice(level, int(zl))
        if (img > intensity_min).sum() > 64:
            occupied.append(int(zl))
    if not occupied:
        raise ValueError("scroll body not found at any probed z")
    return occupied[0] * scale, occupied[-1] * scale
