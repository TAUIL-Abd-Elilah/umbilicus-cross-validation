"""Global umbilicus tracking: per-slice evidence plus a continuity prior, by DP.

Every per-slice estimator tried in this project has the same character — it is
right on some slices and badly wrong on others (lasagna normals: 46 voxels at one
z, 1456 at another).  Picking the per-slice maximum therefore fails, because
nothing stops a slice whose evidence is dominated by a fold from dragging the
answer hundreds of voxels away.

But the umbilicus is smooth: the reference curves move a median of 48-170 voxels
between control points spaced ~200 z apart, i.e. well under one voxel per z.  That
turns the problem into a standard track-through-noisy-detections problem, solved
exactly by dynamic programming over z:

    maximise  sum_z S_z(u_z)  -  lambda * sum_z |u_z - u_{z-1}|^2 / dz

where `S_z` is the per-slice score grid.  Confident slices then pin the track and
propagate their information into the ambiguous ones, which is precisely what a
human does in khartes by scrolling through z.

The DP is exact (no local minima) and runs over a coarse candidate grid, so the
cost is the score grids, not the optimisation.
"""

from __future__ import annotations

import numpy as np


def viterbi_track(
    grids: list[np.ndarray],
    zs: list[float],
    cand_y: np.ndarray,
    cand_x: np.ndarray,
    lam: float = 1.0,
    max_step_per_z: float = 2.0,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Best-scoring smooth path through a stack of per-slice score grids.

    `grids[i]` has shape (len(cand_y), len(cand_x)) and is the evidence at `zs[i]`.
    Returns (y_track, x_track, info) in the same units as `cand_y`/`cand_x`.
    """
    n = len(grids)
    ny, nx = len(cand_y), len(cand_x)
    flat = [g.reshape(-1).astype(np.float64) for g in grids]

    # normalise each slice so one high-contrast slice cannot outvote the rest
    norm = []
    for g in flat:
        lo, hi = np.percentile(g, 5), g.max()
        norm.append((g - lo) / max(hi - lo, 1e-9))

    gy, gx = np.meshgrid(cand_y, cand_x, indexing="ij")
    py, px = gy.reshape(-1), gx.reshape(-1)

    cost = np.full((n, ny * nx), -np.inf)
    back = np.zeros((n, ny * nx), dtype=np.int32)
    cost[0] = norm[0]

    for i in range(1, n):
        dz = max(abs(zs[i] - zs[i - 1]), 1e-6)
        budget = max_step_per_z * dz
        prev = cost[i - 1]
        # transition penalty is separable in y and x, so evaluate it as a
        # (candidate x candidate) distance rather than materialising a 4-D tensor
        best = np.full(ny * nx, -np.inf)
        arg = np.zeros(ny * nx, dtype=np.int32)
        order = np.argsort(prev)[::-1]
        keep = order[: min(len(order), 4000)]      # prune hopeless predecessors
        kp, ky, kx = prev[keep], py[keep], px[keep]
        for j in range(ny * nx):
            d2 = (ky - py[j]) ** 2 + (kx - px[j]) ** 2
            ok = d2 <= budget * budget
            if not ok.any():
                continue
            val = kp[ok] - lam * d2[ok] / dz
            k = int(np.argmax(val))
            best[j] = val[k]
            arg[j] = keep[ok][k]
        cost[i] = best + norm[i]
        back[i] = arg

    end = int(np.argmax(cost[-1]))
    path = [end]
    for i in range(n - 1, 0, -1):
        end = int(back[i, end])
        path.append(end)
    path = path[::-1]

    y_track = np.array([py[p] for p in path])
    x_track = np.array([px[p] for p in path])
    per_slice_best = np.array([float(np.max(g)) for g in flat])
    chosen = np.array([float(flat[i][path[i]]) for i in range(n)])
    info = {
        "score_ratio": (chosen / np.maximum(per_slice_best, 1e-9)).tolist(),
        "total": float(cost[-1].max()),
    }
    return y_track, x_track, info
