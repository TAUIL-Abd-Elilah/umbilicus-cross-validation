"""Honest post-hoc evaluation for the PHerc1218 umbilicus-only A/B.

The evidence channels are deliberately kept separate:

* label-free output geometry: the public ``spiralcheck`` intrinsic report,
  evaluated in both candidate-axis coordinate frames;
* independent scan evidence: identical, blinded surface-on-CT overlays at
  planes frozen before the production runs completed; and
* circular diagnostics: Villa's satisfaction numbers for constraints that the
  optimizer already saw.  These are recorded, but never called validation.

This script does not select a winner.  The blind package can be reviewed
without the private key; unblinding happens only after a reviewer records a
choice and confidence for every frozen plane.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import secrets
import subprocess
import sys
import weakref
from pathlib import Path
from typing import Any

import numpy as np


FROZEN_PLANES = (5264, 5408, 5536, 5664, 5792, 5872, 5952)
DEFAULT_VOLUME = (
    "s3://vesuvius-challenge-open-data/PHerc1218/volumes/"
    "20250521120456-8.640um-1.2m-116keV-masked.zarr"
)
FORMAT = "pherc1218-axis-ab-evaluation-v1"
SPIRALCHECK_COMMIT = "d1b50e2957409a870225fb9f5dcc5e25f7a0f9da"
SHEETCHECK_COMMIT = "7d53893abcc6cc7c0542e483c7266d75ea930885"
_WINDING = re.compile(r"^w\d+(?:_spliced)?(?:_.+)?$")


class EvaluationError(RuntimeError):
    pass


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode(
        "utf-8"
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_head(path: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode:
        raise EvaluationError(f"cannot resolve Git revision for {path}: {result.stderr.strip()}")
    return result.stdout.strip()


def require_clean_commit(path: Path, expected: str, label: str) -> str:
    actual = git_head(path)
    if actual != expected:
        raise EvaluationError(f"{label} is {actual}; expected pinned commit {expected}")
    result = subprocess.run(
        ["git", "-C", str(path), "status", "--porcelain"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode:
        raise EvaluationError(f"cannot inspect {label} worktree: {result.stderr.strip()}")
    if result.stdout.strip():
        raise EvaluationError(f"{label} worktree has uncommitted changes: {path}")
    return actual


def tree_fingerprint(root: Path) -> dict[str, Any]:
    """Bind a report to every byte of a fitted mesh directory."""
    digest = hashlib.sha256()
    count = 0
    total = 0
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        size = path.stat().st_size
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(size.to_bytes(8, "big"))
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        count += 1
        total += size
    if not count:
        raise EvaluationError(f"cannot fingerprint empty tree: {root}")
    return {"file_count": count, "total_bytes": total, "tree_sha256": digest.hexdigest()}


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvaluationError(f"invalid {label} {path}: {error}") from error
    if not isinstance(value, dict):
        raise EvaluationError(f"{label} root must be an object: {path}")
    return value


def _looks_like_meshes(path: Path) -> bool:
    if not path.is_dir():
        return False
    return any(
        child.is_dir()
        and _WINDING.match(child.name)
        and (child / "meta.json").is_file()
        for child in path.iterdir()
    )


def discover_run(path: Path) -> tuple[Path, Path, Path | None]:
    """Return (run root, meshes directory, satisfaction JSON if present)."""
    path = path.resolve(strict=True)
    candidates: list[Path] = []
    if _looks_like_meshes(path):
        candidates.append(path)
    possible_roots = [path]
    possible_roots.extend(child for child in path.iterdir() if child.is_dir())
    for possible_root in possible_roots:
        for parent in (possible_root / "meshes", possible_root):
            if parent.is_dir():
                for child in sorted(parent.iterdir()):
                    if child.is_dir() and _looks_like_meshes(child):
                        candidates.append(child)
    unique = list(dict.fromkeys(item.resolve() for item in candidates))
    if len(unique) != 1:
        raise EvaluationError(
            f"expected one fitted meshes directory under {path}, found {len(unique)}: {unique}"
        )
    meshes = unique[0]
    run_root = meshes.parent.parent if meshes.parent.name == "meshes" else path
    satisfaction = run_root / "satisfied_fitted.json"
    return run_root, meshes, satisfaction if satisfaction.is_file() else None


def aggregate_satisfaction(value: dict[str, Any]) -> dict[str, Any]:
    """Compact Villa diagnostics without turning training inputs into truth."""
    patches = value.get("patches", [])
    pcls = value.get("pcls", [])
    if not isinstance(patches, list) or not isinstance(pcls, list):
        raise EvaluationError("Villa satisfaction JSON has invalid patches/pcls lists")

    patch_satisfied = sum(float(item.get("satisfied_area", 0.0)) for item in patches)
    patch_total = sum(float(item.get("total_area", 0.0)) for item in patches)
    groups: dict[str, dict[str, int]] = {}
    for item in pcls:
        source = Path(str(item.get("source_file", "unknown"))).name or "unknown"
        group = groups.setdefault(
            source, {"collections": 0, "satisfied_points": 0, "total_points": 0}
        )
        group["collections"] += 1
        group["satisfied_points"] += int(item.get("satisfied_points", 0))
        group["total_points"] += int(item.get("total_points", 0))
    for group in groups.values():
        total = group["total_points"]
        group["fraction"] = group["satisfied_points"] / total if total else None

    return {
        "interpretation": (
            "CIRCULAR DIAGNOSTIC ONLY: these patches/PCLs were optimizer inputs and "
            "are not held-out evidence."
        ),
        "patches": {
            "count": len(patches),
            "satisfied_area": patch_satisfied,
            "total_area": patch_total,
            "weighted_fraction": patch_satisfied / patch_total if patch_total else None,
        },
        "pcls_by_source_file": groups,
        "unverified_patch_count": len(value.get("unverified_patches", [])),
    }


def blind_assignment(seed: int) -> dict[str, str]:
    arms = ["baseline", "manual"]
    random.Random(seed).shuffle(arms)
    return {"A": arms[0], "B": arms[1]}


def axis_yx_at_z(axis: dict[str, Any], z: float) -> np.ndarray:
    points = axis.get("control_points")
    if not isinstance(points, list) or len(points) < 2:
        raise EvaluationError("axis must contain at least two control_points")
    rows = np.asarray(
        [[float(item["z"]), float(item["y"]), float(item["x"])] for item in points],
        dtype=np.float64,
    )
    rows = rows[np.argsort(rows[:, 0])]
    return np.asarray(
        [np.interp(z, rows[:, 0], rows[:, 1]), np.interp(z, rows[:, 0], rows[:, 2])]
    )


def median_radial_gap_l1(
    family: dict[int, Any], axis: dict[str, Any], plane: float
) -> dict[str, Any]:
    """Median adjacent-winding radial gap at one plane, reported at CT L1."""
    centre_y, centre_x = axis_yx_at_z(axis, plane)
    radii: dict[int, float] = {}
    for winding, surface in sorted(family.items()):
        segments, _ = plane_segments({winding: surface}, plane)
        if not len(segments):
            continue
        points = segments.reshape(-1, 2)
        radius = np.hypot(points[:, 0] - centre_x, points[:, 1] - centre_y)
        if np.isfinite(radius).any():
            radii[winding] = float(np.median(radius[np.isfinite(radius)]))
    gaps: list[float] = []
    used_pairs: list[list[int]] = []
    windings = sorted(radii)
    for inner, outer in zip(windings, windings[1:]):
        delta = outer - inner
        if delta <= 0:
            continue
        gap_l0 = (radii[outer] - radii[inner]) / delta
        if math.isfinite(gap_l0) and gap_l0 > 0:
            gaps.append(gap_l0 / 2.0)
            used_pairs.append([inner, outer])
    if not gaps:
        raise EvaluationError(f"no positive adjacent-winding gaps at z={plane}")
    return {
        "z_l0": int(plane),
        "median_radial_gap_l1": float(np.median(gaps)),
        "pair_count": len(gaps),
        "winding_id_span": [used_pairs[0][0], used_pairs[-1][1]],
    }


def admission_gate_from_metrics(
    *,
    relative_fraction: float | None,
    same_fraction: float | None,
    patch_count: int,
    radial_gap_records: list[dict[str, Any]],
) -> dict[str, Any]:
    checks = {
        "relative_points_at_least_94pct": bool(
            relative_fraction is not None and relative_fraction >= 0.94
        ),
        "same_winding_points_at_least_91pct": bool(
            same_fraction is not None and same_fraction >= 0.91
        ),
        "exactly_3_intersecting_patches": patch_count == 3,
        "all_3_radial_gaps_l1_in_9p6_10p6": bool(
            len(radial_gap_records) == 3
            and all(
                9.6 <= float(record["median_radial_gap_l1"]) <= 10.6
                for record in radial_gap_records
            )
        ),
    }
    return {
        "interpretation": (
            "CIRCULAR/RUN-HEALTH ADMISSION ONLY: proves the fit honored its input "
            "constraints and retained plausible pitch; it is not an accuracy score."
        ),
        "thresholds": {
            "relative_fraction_min": 0.94,
            "same_winding_fraction_min": 0.91,
            "intersecting_patch_count": 3,
            "radial_gap_l1_inclusive": [9.6, 10.6],
            "radial_gap_z_l0": [5420, 5620, 5820],
        },
        "observed": {
            "relative_fraction": relative_fraction,
            "same_winding_fraction": same_fraction,
            "intersecting_patch_count": patch_count,
            "radial_gaps": radial_gap_records,
        },
        "checks": checks,
        "passed": all(checks.values()),
    }


def run_health_gate(
    satisfaction: dict[str, Any], family: dict[int, Any], axis: dict[str, Any]
) -> dict[str, Any]:
    groups = satisfaction["pcls_by_source_file"]
    relative = groups.get("relative_windings.json", {}).get("fraction")
    same = groups.get("same_windings.json", {}).get("fraction")
    gaps = [median_radial_gap_l1(family, axis, z) for z in (5420, 5620, 5820)]
    return admission_gate_from_metrics(
        relative_fraction=relative,
        same_fraction=same,
        patch_count=int(satisfaction["patches"]["count"]),
        radial_gap_records=gaps,
    )


def surface_geometry_summary(family: dict[int, Any]) -> dict[str, Any]:
    if len(family) < 2:
        raise EvaluationError("geometry summary needs at least two windings")
    valid_vertices = total_vertices = valid_quads = total_quads = 0
    lo = np.full(3, np.inf)
    hi = np.full(3, -np.inf)
    for surface in family.values():
        valid = surface.valid_vertex_mask
        valid_vertices += int(valid.sum())
        total_vertices += int(valid.size)
        quads = surface.valid_quad_mask
        valid_quads += int(quads.sum())
        total_quads += int(quads.size)
        points = surface.valid_zyxs.astype(np.float64, copy=False)
        lo = np.minimum(lo, points.min(axis=0))
        hi = np.maximum(hi, points.max(axis=0))
    return {
        "interpretation": (
            "LABEL-FREE OUTPUT GEOMETRY: detects topology/coverage failures but is not "
            "an anatomical ground truth score."
        ),
        "winding_count": len(family),
        "winding_id_range": [min(family), max(family)],
        "valid_vertices": valid_vertices,
        "total_vertices": total_vertices,
        "valid_vertex_fraction": valid_vertices / total_vertices,
        "valid_quads": valid_quads,
        "total_quads": total_quads,
        "valid_quad_fraction": valid_quads / total_quads,
        "bbox_zyx": [lo.tolist(), hi.tolist()],
    }


def plane_segments(family: dict[int, Any], plane: float) -> tuple[np.ndarray, int]:
    """March valid tifxyz quads and return XY line segments at one Z plane.

    The half-open edge rule assigns vertices exactly on the plane once and
    avoids duplicate contours.  Four-hit saddle quads emit two segments and
    are counted so the report exposes this otherwise hidden ambiguity.
    """
    all_segments: list[np.ndarray] = []
    ambiguous = 0
    for surface in family.values():
        p = np.asarray(surface.zyxs, dtype=np.float64)
        quad_ok = np.asarray(surface.valid_quad_mask, dtype=bool)
        corners = (p[:-1, :-1], p[:-1, 1:], p[1:, 1:], p[1:, :-1])
        edges = ((0, 1), (1, 2), (2, 3), (3, 0))
        hits = np.full((*quad_ok.shape, 4, 2), np.nan, dtype=np.float64)
        for edge_index, (first, second) in enumerate(edges):
            a, b = corners[first], corners[second]
            za, zb = a[..., 0], b[..., 0]
            crosses = quad_ok & (
                ((za < plane) & (zb >= plane)) | ((zb < plane) & (za >= plane))
            )
            denom = zb - za
            crosses &= np.abs(denom) > 1e-12
            if not crosses.any():
                continue
            t = np.zeros_like(za)
            t[crosses] = (plane - za[crosses]) / denom[crosses]
            y = a[..., 1] + t * (b[..., 1] - a[..., 1])
            x = a[..., 2] + t * (b[..., 2] - a[..., 2])
            hits[..., edge_index, 0][crosses] = x[crosses]
            hits[..., edge_index, 1][crosses] = y[crosses]

        present = np.isfinite(hits[..., 0])
        for row, col in np.argwhere(present.sum(axis=-1) >= 2):
            points = hits[row, col, present[row, col]]
            if len(points) > 2:
                ambiguous += 1
            for start in range(0, len(points) - 1, 2):
                segment = points[start : start + 2]
                if len(segment) == 2 and not np.allclose(segment[0], segment[1]):
                    all_segments.append(segment)
    if not all_segments:
        return np.empty((0, 2, 2), dtype=np.float64), ambiguous
    return np.stack(all_segments), ambiguous


def common_crop(
    families: dict[str, dict[int, Any]], *, margin: int = 96
) -> tuple[int, int, int, int]:
    lo = np.full(2, np.inf)
    hi = np.full(2, -np.inf)
    for family in families.values():
        for surface in family.values():
            points = surface.valid_zyxs.astype(np.float64, copy=False)
            lo = np.minimum(lo, points[:, 1:].min(axis=0))
            hi = np.maximum(hi, points[:, 1:].max(axis=0))
    if not np.isfinite(lo).all() or not np.isfinite(hi).all():
        raise EvaluationError("cannot derive a finite common CT crop")
    y0, x0 = np.floor(lo - margin).astype(int)
    y1, x1 = np.ceil(hi + margin).astype(int)
    return int(y0), int(y1), int(x0), int(x1)


def align_crop_to_level(
    crop_l0: tuple[int, int, int, int],
    *,
    scale: int,
    shape_yx: tuple[int, int],
) -> tuple[int, int, int, int]:
    """Expand a level-0 crop to exact pyramid-pixel boundaries."""
    if scale <= 0:
        raise EvaluationError("CT scale must be positive")
    y0, y1, x0, x1 = crop_l0
    max_y, max_x = shape_yx[0] * scale, shape_yx[1] * scale
    y0 = max(0, (y0 // scale) * scale)
    x0 = max(0, (x0 // scale) * scale)
    y1 = min(max_y, ((y1 + scale - 1) // scale) * scale)
    x1 = min(max_x, ((x1 + scale - 1) // scale) * scale)
    if y1 <= y0 or x1 <= x0:
        raise EvaluationError(f"empty aligned CT crop: {(y0, y1, x0, x1)}")
    return y0, y1, x0, x1


def image_extent_l0(
    crop_l0: tuple[int, int, int, int], scale: int
) -> tuple[float, float, float, float]:
    """Matplotlib extent whose pixel centres remain on pyramid-grid indices."""
    y0, y1, x0, x1 = crop_l0
    half = scale / 2.0
    return x0 - half, x1 - half, y1 - half, y0 - half


def _render_one(
    ct: np.ndarray,
    segments: np.ndarray,
    *,
    crop_l0: tuple[int, int, int, int],
    level: int,
    label: str,
    plane: int,
    display_range: tuple[float, float],
    output: Path,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection

    scale = 2**level
    extent = image_extent_l0(crop_l0, scale)
    fig, axis = plt.subplots(figsize=(12, 12), dpi=240, constrained_layout=True)
    axis.imshow(
        ct,
        cmap="gray",
        vmin=display_range[0],
        vmax=display_range[1],
        origin="upper",
        extent=extent,
        interpolation="nearest",
    )
    if len(segments):
        axis.add_collection(
            LineCollection(segments, colors="#00e5ff", linewidths=0.42, alpha=0.92)
        )
    axis.set(xlim=extent[:2], ylim=extent[2:], aspect="equal")
    axis.set_title(f"candidate {label} | PHerc1218 z={plane} | CT L{level}")
    axis.set_xlabel("x (level-0 voxels)")
    axis.set_ylabel("y (level-0 voxels)")
    fig.savefig(output, facecolor="white")
    plt.close(fig)


def _render_pair(
    ct: np.ndarray,
    labelled_segments: dict[str, np.ndarray],
    *,
    crop_l0: tuple[int, int, int, int],
    level: int,
    plane: int,
    display_range: tuple[float, float],
    output: Path,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection

    scale = 2**level
    extent = image_extent_l0(crop_l0, scale)
    fig, axes = plt.subplots(1, 2, figsize=(20, 10), dpi=240, constrained_layout=True)
    for axis, label in zip(axes, ("A", "B"), strict=True):
        axis.imshow(
            ct,
            cmap="gray",
            vmin=display_range[0],
            vmax=display_range[1],
            origin="upper",
            extent=extent,
            interpolation="nearest",
        )
        if len(labelled_segments[label]):
            axis.add_collection(
                LineCollection(
                    labelled_segments[label], colors="#00e5ff", linewidths=0.42, alpha=0.92
                )
            )
        axis.set(xlim=extent[:2], ylim=extent[2:], aspect="equal")
        axis.set_title(f"candidate {label}")
        axis.set_xlabel("x (level-0 voxels)")
        axis.set_ylabel("y (level-0 voxels)")
    fig.suptitle(f"PHerc1218 z={plane} | identical CT L{level} and display range")
    fig.savefig(output, facecolor="white")
    plt.close(fig)


def make_blind_overlays(
    families: dict[str, dict[int, Any]],
    *,
    assignment: dict[str, str],
    volume_path: str,
    level: int,
    output: Path,
    sheetcheck_repo: Path,
) -> tuple[list[dict[str, Any]], tuple[int, int, int, int]]:
    sys.path.insert(0, str(sheetcheck_repo))
    from sheetcheck.io import Volume

    common_windings = sorted(set.intersection(*(set(family) for family in families.values())))
    if len(common_windings) < 2:
        raise EvaluationError("the two arms have fewer than two common winding IDs")
    # The frozen visual contract requires the same winding range. Do not let an
    # arm's extra outer windings enlarge its crop or add lines only on one side.
    visual_families = {
        arm: {winding: family[winding] for winding in common_windings}
        for arm, family in families.items()
    }
    crop = common_crop(visual_families)
    volume = Volume(volume_path, level=level)
    array = volume.array
    scale = 2**level
    crop = align_crop_to_level(
        crop,
        scale=scale,
        shape_yx=(int(array.shape[1]), int(array.shape[2])),
    )
    y0, y1, x0, x1 = crop
    ly0, ly1 = y0 // scale, y1 // scale
    lx0, lx1 = x0 // scale, x1 // scale

    output.mkdir(parents=True, exist_ok=True)
    # Fetch each touched z-chunk only once. Reading seven isolated planes would
    # otherwise re-download the same compressed 3-D chunks several times.
    level_planes = {plane: plane // scale for plane in FROZEN_PLANES}
    chunk_depth = int(array.chunks[0])
    groups: dict[int, list[tuple[int, int]]] = {}
    for plane, level_z in level_planes.items():
        groups.setdefault(level_z // chunk_depth, []).append((plane, level_z))
    ct_planes: dict[int, np.ndarray] = {}
    for members in groups.values():
        z0 = min(level_z for _, level_z in members)
        z1 = max(level_z for _, level_z in members) + 1
        slab = np.asarray(array[z0:z1, ly0:ly1, lx0:lx1])
        for plane, level_z in members:
            ct_planes[plane] = np.asarray(slab[level_z - z0]).copy()
        del slab

    records: list[dict[str, Any]] = []
    for plane in FROZEN_PLANES:
        if plane % scale:
            raise EvaluationError(
                f"frozen plane {plane} is not exactly represented at CT level {level}"
            )
        level_z = plane // scale
        ct = ct_planes[plane]
        if ct.ndim != 2 or not ct.size:
            raise EvaluationError(f"empty CT plane at z={plane}")
        positive = ct[ct > 0]
        source = positive if positive.size >= 100 else ct.reshape(-1)
        vmin, vmax = np.percentile(source, [1.0, 99.5]).astype(float)
        if not math.isfinite(vmin) or not math.isfinite(vmax) or vmax <= vmin:
            raise EvaluationError(f"invalid CT display range at z={plane}: {vmin}, {vmax}")

        by_arm: dict[str, np.ndarray] = {}
        ambiguity: dict[str, int] = {}
        for arm, family in visual_families.items():
            by_arm[arm], ambiguity[arm] = plane_segments(family, plane)
        by_label = {label: by_arm[arm] for label, arm in assignment.items()}
        single_files: dict[str, str] = {}
        for label in ("A", "B"):
            filename = f"z{plane:05d}_{label}.png"
            _render_one(
                ct,
                by_label[label],
                crop_l0=crop,
                level=level,
                label=label,
                plane=plane,
                display_range=(vmin, vmax),
                output=output / filename,
            )
            single_files[label] = filename
        pair_file = f"z{plane:05d}_AB.png"
        _render_pair(
            ct,
            by_label,
            crop_l0=crop,
            level=level,
            plane=plane,
            display_range=(vmin, vmax),
            output=output / pair_file,
        )
        records.append(
            {
                "z_l0": plane,
                "z_at_level": level_z,
                "ct_sha256": hashlib.sha256(ct.tobytes(order="C")).hexdigest(),
                "ct_shape": list(ct.shape),
                "ct_dtype": str(ct.dtype),
                "display_percentiles": [1.0, 99.5],
                "display_range": [vmin, vmax],
                "files": {**single_files, "paired": pair_file},
                "segment_counts_by_blind_label": {
                    label: int(len(by_label[label])) for label in ("A", "B")
                },
                "ambiguous_quad_counts_by_arm_private": ambiguity,
            }
        )
    store = getattr(array, "store", None)
    fs = getattr(store, "fs", None)
    if fs is not None:
        finalizers = []
        for finalizer in list(weakref.finalize._registry):
            state = finalizer.peek()
            if state is not None and state[0] is fs:
                finalizers.append(finalizer)
        if len(finalizers) == 1:
            finalizers[0]()
        else:
            try:
                fs.close_session(fs.loop, fs.s3)
            except Exception:
                pass
    if store is not None:
        store.close()
    return records, crop


def run(args: argparse.Namespace) -> dict[str, Any]:
    spiralcheck = args.spiralcheck.resolve(strict=True)
    sheetcheck = args.sheetcheck.resolve(strict=True)
    spiralcheck_commit = require_clean_commit(
        spiralcheck, SPIRALCHECK_COMMIT, "spiralcheck"
    )
    sheetcheck_commit = require_clean_commit(sheetcheck, SHEETCHECK_COMMIT, "sheetcheck")
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        raise EvaluationError(f"refusing to overwrite non-empty evaluation output: {out}")
    sys.path.insert(0, str(spiralcheck / "src"))
    from spiralcheck.intrinsic import intrinsic_report
    from spiralcheck.io_tifxyz import load_run_windings

    discoveries = {
        arm: discover_run(path)
        for arm, path in (("baseline", args.baseline_run), ("manual", args.manual_run))
    }
    families = {
        arm: load_run_windings(meshes, variant="spliced")
        for arm, (_, meshes, _) in discoveries.items()
    }
    axes = {
        "baseline_axis": load_json(args.baseline_umbilicus.resolve(strict=True), "baseline axis"),
        "manual_axis": load_json(args.manual_umbilicus.resolve(strict=True), "manual axis"),
    }

    label_free = {
        "interpretation": (
            "No patch/PCL labels are used. Intrinsic radial ordering depends on the chosen axis, "
            "so both candidate axes are reported and a favorable direction is robust only if it "
            "does not flip between frames. These metrics detect defects; they do not establish "
            "anatomical correctness."
        ),
        "axis_free_summaries": {
            arm: surface_geometry_summary(family) for arm, family in families.items()
        },
        "spiralcheck_intrinsic_by_axis_frame": {
            frame: {
                arm: intrinsic_report(family, axis, z_bins=10, theta_bins=48).to_dict()
                for arm, family in families.items()
            }
            for frame, axis in axes.items()
        },
        "primary_own_axis": {
            "baseline": intrinsic_report(
                families["baseline"], axes["baseline_axis"], z_bins=10, theta_bins=48
            ).to_dict(),
            "manual": intrinsic_report(
                families["manual"], axes["manual_axis"], z_bins=10, theta_bins=48
            ).to_dict(),
        },
    }

    circular: dict[str, Any] = {}
    run_health: dict[str, Any] = {}
    for arm, (_, _, satisfaction) in discoveries.items():
        if satisfaction is None:
            circular[arm] = {"available": False}
            run_health[arm] = {"available": False, "passed": False}
            continue
        circular[arm] = aggregate_satisfaction(
            load_json(satisfaction, f"{arm} satisfaction")
        )
        run_health[arm] = run_health_gate(
            circular[arm], families[arm], axes[f"{arm}_axis"]
        )

    blind_seed = args.blind_seed if args.blind_seed is not None else secrets.randbits(64)
    assignment = blind_assignment(blind_seed)
    analysis_dir = out / "analysis"
    blind_dir = out / "blind"
    private_dir = out / "private"
    for directory in (analysis_dir, blind_dir, private_dir):
        directory.mkdir(parents=True, exist_ok=True)

    overlay_records: list[dict[str, Any]] = []
    crop = None
    if not args.skip_ct:
        overlay_records, crop = make_blind_overlays(
            families,
            assignment=assignment,
            volume_path=args.volume,
            level=args.ct_level,
            output=blind_dir,
            sheetcheck_repo=sheetcheck,
        )

    key = {
        "format": FORMAT,
        "seed": blind_seed,
        "assignment": assignment,
        "warning": "Do not share or open until the frozen review form is complete.",
    }
    (private_dir / "blind_key.json").write_bytes(canonical_json(key))
    key_sha256 = sha256_file(private_dir / "blind_key.json")

    public_manifest = {
        "format": FORMAT,
        "evidence_type": "independent exact-scan visual review",
        "interpretation": (
            "A and B use byte-identical CT pixels, crop, contrast, colour, line width and scale. "
            "The overlays support blinded visual review; they are not a quantitative "
            "ground-truth score."
        ),
        "frozen_planes_l0": list(FROZEN_PLANES),
        "volume": args.volume,
        "ct_level": args.ct_level,
        "common_crop_l0_y0_y1_x0_x1": list(crop) if crop else None,
        "planes": [
            {key: value for key, value in record.items() if not key.endswith("_private")}
            for record in overlay_records
        ],
        "private_key_sha256": key_sha256,
        "review_form": [
            {
                "z_l0": plane,
                "preference": "A | B | tie | unusable",
                "confidence": "low | medium | high",
                "reason": "continuity / sheet-centering / crossing / other",
            }
            for plane in FROZEN_PLANES
        ],
        "unblind_rule": (
            "Record all seven preferences and confidence levels before opening "
            "private/blind_key.json."
        ),
    }
    (blind_dir / "manifest.json").write_bytes(canonical_json(public_manifest))

    report = {
        "format": FORMAT,
        "claim_boundary": (
            "No winner is selected. Constraint satisfaction is circular; intrinsic geometry is "
            "label-free defect detection; CT overlays require a blinded human judgment."
        ),
        "inputs": {
            arm: {
                "run_root": str(run_root),
                "meshes": str(meshes),
                "mesh_tree": tree_fingerprint(meshes),
                "satisfaction": str(satisfaction) if satisfaction else None,
                "satisfaction_sha256": sha256_file(satisfaction) if satisfaction else None,
                "axis_sha256": sha256_file(
                    args.baseline_umbilicus.resolve(strict=True)
                    if arm == "baseline"
                    else args.manual_umbilicus.resolve(strict=True)
                ),
            }
            for arm, (run_root, meshes, satisfaction) in discoveries.items()
        },
        "public_reuse": {
            "spiralcheck": {
                "repository": "https://github.com/Nicodol/spiralcheck",
                "commit": spiralcheck_commit,
                "role": "label-free intrinsic geometry",
            },
            "sheetcheck": {
                "repository": "https://github.com/DomRusso2/sheetcheck",
                "commit": sheetcheck_commit,
                "role": "lazy exact-CT access only",
            },
        },
        "label_free_geometry": label_free,
        "circular_constraint_diagnostics": circular,
        "run_health_admission": run_health,
        "blind_package": {
            "manifest": str(blind_dir / "manifest.json"),
            "manifest_sha256": sha256_file(blind_dir / "manifest.json"),
            "private_key": str(private_dir / "blind_key.json"),
            "overlays_generated": not args.skip_ct,
        },
    }
    (analysis_dir / "report.json").write_bytes(canonical_json(report))
    return report


def parser() -> argparse.ArgumentParser:
    here = Path(__file__).resolve().parent
    root = here.parents[2]
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--baseline-run", type=Path, required=True)
    result.add_argument("--manual-run", type=Path, required=True)
    result.add_argument("--baseline-umbilicus", type=Path, required=True)
    result.add_argument("--manual-umbilicus", type=Path, required=True)
    result.add_argument("--out", type=Path, required=True)
    result.add_argument(
        "--spiralcheck",
        type=Path,
        default=root / "_external_overlap_review_20260809" / "spiralcheck",
    )
    result.add_argument(
        "--sheetcheck",
        type=Path,
        default=root / "_external_overlap_review_20260809" / "sheetcheck",
    )
    result.add_argument("--volume", default=DEFAULT_VOLUME)
    result.add_argument("--ct-level", type=int, choices=(0, 1, 2, 3), default=1)
    result.add_argument(
        "--blind-seed",
        type=int,
        default=None,
        help="Testing/reproduction only. Omit for a cryptographically random private mapping.",
    )
    result.add_argument(
        "--skip-ct",
        action="store_true",
        help="Run geometry/constraint plumbing only; never use this for the production report.",
    )
    return result


def main() -> int:
    args = parser().parse_args()
    run(args)
    print(f"wrote {args.out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
