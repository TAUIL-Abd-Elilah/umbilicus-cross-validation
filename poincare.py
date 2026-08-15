"""Locate the umbilicus as a singularity of the sheet-orientation field.

Motivation
----------
PROTOCOL.md Amendment 02 concluded that the umbilicus is a *topological* property
of the winding rather than a local appearance feature.  That conclusion suggests
its own instrument: the Poincaré index.

Sheets in a scroll cross-section form a line field (orientation mod pi), exactly
like fingerprint ridges.  Walking a closed loop around a point and accumulating
the change in sheet orientation gives an integer-valued index that is invariant
under deformation:

    index(u) = (1 / 2pi) * sum_loop  wrap( theta(p_{k+1}) - theta(p_k) )

with each difference wrapped into (-pi/2, pi/2] because the field is a line field,
not a vector field.  Concentric windings about a centre rotate the orientation by
a full turn, giving index +1 there and 0 almost everywhere else.  This is the
standard fingerprint core/delta detector, and a crushed scroll is morphologically
a fingerprint.

Because the index is topological it does not care that the lamellae are squashed
and non-circular — which is precisely why the earlier radial-alignment score
failed.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from umbilicus_estimator import EstimatorConfig, structure_tensor_normals


def orientation_field(img: np.ndarray, cfg: EstimatorConfig) -> tuple[np.ndarray, np.ndarray]:
    """Sheet orientation theta in [0, pi) and a coherence weight."""
    normals, coherence = structure_tensor_normals(img, cfg)
    # normal direction -> sheet (tangent) direction is a 90 deg rotation, which is
    # a constant offset and so does not change the index; keep the normal angle.
    theta = np.arctan2(normals[..., 0], normals[..., 1]) % np.pi
    return theta.astype(np.float32), coherence


def _wrap_half_pi(d: np.ndarray) -> np.ndarray:
    """Wrap angle differences of a line field into (-pi/2, pi/2]."""
    return (d + np.pi / 2.0) % np.pi - np.pi / 2.0


def poincare_index(
    theta: np.ndarray,
    radius: float = 12.0,
    n_samples: int = 32,
    smooth_sigma: float = 2.0,
) -> np.ndarray:
    """Dense Poincaré index of the line field `theta`, on a loop of `radius` px.

    Returns an array the same shape as `theta`; +1 marks a winding centre.
    """
    # Smoothing a line field must be done on the doubled angle, otherwise values
    # near 0 and pi cancel instead of reinforcing.
    if smooth_sigma > 0:
        c = ndimage.gaussian_filter(np.cos(2 * theta), smooth_sigma)
        s = ndimage.gaussian_filter(np.sin(2 * theta), smooth_sigma)
        theta = 0.5 * np.arctan2(s, c)

    ang = np.linspace(0.0, 2.0 * np.pi, n_samples, endpoint=False)
    offs = [(radius * np.sin(a), radius * np.cos(a)) for a in ang]

    yy, xx = np.mgrid[0 : theta.shape[0], 0 : theta.shape[1]].astype(np.float32)
    samples = []
    for dy, dx in offs:
        samples.append(
            ndimage.map_coordinates(
                theta, [yy + dy, xx + dx], order=1, mode="nearest"
            )
        )
    samples.append(samples[0])  # close the loop

    total = np.zeros_like(theta, dtype=np.float32)
    for k in range(n_samples):
        total += _wrap_half_pi(samples[k + 1] - samples[k])
    return total / (2.0 * np.pi)


def find_core(
    img: np.ndarray,
    cfg: EstimatorConfig,
    radii=(8.0, 12.0, 18.0, 26.0),
    coherence_min: float = 0.15,
) -> dict:
    """Find the strongest +1 singularity of the sheet field in `img`.

    Averaging the index over several loop radii suppresses spurious singularities
    from local damage, which survive at one scale but not across scales.
    """
    theta, coherence = orientation_field(img, cfg)
    acc = np.zeros_like(theta, dtype=np.float32)
    for r in radii:
        acc += poincare_index(theta, radius=r)
    acc /= len(radii)

    # a real winding centre is a +1 index sitting in well-oriented material
    valid = ndimage.gaussian_filter(coherence, 3.0) > coherence_min
    scored = np.where(valid, acc, 0.0)
    scored = ndimage.gaussian_filter(scored, 2.0)

    iy, ix = np.unravel_index(int(np.argmax(scored)), scored.shape)
    return {
        "y": float(iy),
        "x": float(ix),
        "index": float(scored[iy, ix]),
        "raw_index": float(acc[iy, ix]),
        "field": scored,
    }
