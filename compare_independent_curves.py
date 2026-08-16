#!/usr/bin/env python3
"""Compare two independently annotated Villa umbilicus sets at identical z.

This tool measures disagreement; it does not decide which annotation is right.
Both polylines are linearly interpolated only over their shared z range and the
lateral (x, y) distance is reported in voxels and millimetres.  Large-distance
locations are emitted as CT-review candidates, never as automatic corrections.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from scrolls import SCROLLS


FORMAT = "independent-umbilicus-comparison-v1"
DEFAULT_SCROLLS = (
    "PHerc0191",
    "PHerc0257",
    "PHerc0358",
    "PHerc0800",
    "PHerc0813",
    "PHerc1203",
)


class ComparisonError(ValueError):
    """Raised when input curves cannot be compared safely."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ComparisonError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_curve(path: Path) -> np.ndarray:
    require(path.is_file(), f"missing curve: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ComparisonError(f"invalid JSON: {path}") from error
    require(isinstance(value, dict), f"curve root must be an object: {path}")
    controls = value.get("control_points")
    require(isinstance(controls, list) and len(controls) >= 2, f"curve needs at least two controls: {path}")
    rows: list[tuple[float, float, float]] = []
    for index, control in enumerate(controls):
        require(isinstance(control, dict), f"control {index} is not an object: {path}")
        try:
            row = (float(control["x"]), float(control["y"]), float(control["z"]))
        except (KeyError, TypeError, ValueError) as error:
            raise ComparisonError(f"control {index} lacks numeric x/y/z: {path}") from error
        require(all(np.isfinite(row)), f"control {index} is not finite: {path}")
        rows.append(row)
    points = np.asarray(rows, dtype=np.float64)
    require(bool(np.all(np.diff(points[:, 2]) > 0)), f"control z must be unique and increasing: {path}")
    return points


def interpolate_xy(points: np.ndarray, z: np.ndarray) -> np.ndarray:
    require(points.ndim == 2 and points.shape[1] == 3, "points must be an Nx3 array")
    require(bool(np.all(z >= points[0, 2]) and np.all(z <= points[-1, 2])), "z lies outside curve range")
    return np.column_stack(
        (
            np.interp(z, points[:, 2], points[:, 0]),
            np.interp(z, points[:, 2], points[:, 1]),
        )
    )


def quantile(values: np.ndarray, q: float) -> float:
    return float(np.quantile(values, q, method="linear"))


def disagreement_bands(
    z: np.ndarray,
    distance_mm: np.ndarray,
    threshold_mm: float,
) -> list[dict[str, Any]]:
    """Return contiguous above-threshold ranges, highest peak first."""
    mask = distance_mm >= threshold_mm
    if not np.any(mask):
        return []
    indices = np.flatnonzero(mask)
    split_at = np.flatnonzero(np.diff(indices) > 1) + 1
    groups = np.split(indices, split_at)
    bands = []
    for group in groups:
        local = int(group[np.argmax(distance_mm[group])])
        bands.append(
            {
                "z_start": int(z[group[0]]),
                "z_end": int(z[group[-1]]),
                "peak_z": int(z[local]),
                "peak_distance_mm": float(distance_mm[local]),
            }
        )
    return sorted(bands, key=lambda row: (-row["peak_distance_mm"], row["peak_z"]))


def review_candidates(
    z: np.ndarray,
    ours_xy: np.ndarray,
    reference_xy: np.ndarray,
    distance_voxels: np.ndarray,
    voxel_size_um: float,
    count: int,
    separation_z: int,
) -> list[dict[str, Any]]:
    """Select the largest disagreements while spacing candidates in z."""
    chosen: list[int] = []
    for index in np.argsort(-distance_voxels, kind="stable"):
        i = int(index)
        if all(abs(int(z[i]) - int(z[j])) >= separation_z for j in chosen):
            chosen.append(i)
            if len(chosen) == count:
                break
    return [
        {
            "z": int(z[i]),
            "ours_xy": [float(ours_xy[i, 0]), float(ours_xy[i, 1])],
            "reference_xy": [float(reference_xy[i, 0]), float(reference_xy[i, 1])],
            "distance_voxels": float(distance_voxels[i]),
            "distance_mm": float(distance_voxels[i] * voxel_size_um / 1000.0),
            "status": "requires_exact_ct_review",
        }
        for i in chosen
    ]


def compare_one(
    scroll: str,
    ours_path: Path,
    reference_path: Path,
    *,
    sample_step_z: int = 1,
    candidate_count: int = 3,
    candidate_separation_z: int = 750,
    reporting_threshold_mm: float = 1.81,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    require(scroll in SCROLLS, f"unknown scroll: {scroll}")
    require(sample_step_z >= 1, "sample_step_z must be positive")
    require(candidate_count >= 1, "candidate_count must be positive")
    require(candidate_separation_z >= 1, "candidate_separation_z must be positive")
    require(reporting_threshold_mm >= 0, "reporting_threshold_mm must be non-negative")
    ours = load_curve(ours_path)
    reference = load_curve(reference_path)
    lo = int(np.ceil(max(ours[0, 2], reference[0, 2])))
    hi = int(np.floor(min(ours[-1, 2], reference[-1, 2])))
    require(lo <= hi, f"curves have no shared z range: {scroll}")
    z = np.arange(lo, hi + 1, sample_step_z, dtype=np.int64)
    if z[-1] != hi:
        z = np.append(z, hi)
    ours_xy = interpolate_xy(ours, z)
    reference_xy = interpolate_xy(reference, z)
    delta = ours_xy - reference_xy
    distances = np.linalg.norm(delta, axis=1)
    voxel_size_um = float(SCROLLS[scroll]["um"])
    distance_mm = distances * voxel_size_um / 1000.0
    max_index = int(np.argmax(distances))

    rows = [
        {
            "scroll": scroll,
            "z": int(z[i]),
            "ours_x": float(ours_xy[i, 0]),
            "ours_y": float(ours_xy[i, 1]),
            "reference_x": float(reference_xy[i, 0]),
            "reference_y": float(reference_xy[i, 1]),
            "distance_voxels": float(distances[i]),
            "distance_mm": float(distance_mm[i]),
        }
        for i in range(len(z))
    ]
    metrics = {
        "scroll": scroll,
        "voxel_size_um": voxel_size_um,
        "ours": {
            "file": ours_path.name,
            "sha256": sha256(ours_path),
            "control_count": int(len(ours)),
            "z_range": [float(ours[0, 2]), float(ours[-1, 2])],
        },
        "reference": {
            "file": reference_path.name,
            "sha256": sha256(reference_path),
            "control_count": int(len(reference)),
            "z_range": [float(reference[0, 2]), float(reference[-1, 2])],
        },
        "shared_z_range": [lo, hi],
        "sample_step_z": sample_step_z,
        "sample_count": int(len(z)),
        "distance": {
            "median_voxels": float(np.median(distances)),
            "mean_voxels": float(np.mean(distances)),
            "p90_voxels": quantile(distances, 0.90),
            "p95_voxels": quantile(distances, 0.95),
            "max_voxels": float(distances[max_index]),
            "max_z": int(z[max_index]),
            "median_mm": float(np.median(distance_mm)),
            "mean_mm": float(np.mean(distance_mm)),
            "p90_mm": quantile(distance_mm, 0.90),
            "p95_mm": quantile(distance_mm, 0.95),
            "max_mm": float(distance_mm[max_index]),
        },
        "reporting_threshold": {
            "mm": reporting_threshold_mm,
            "purpose": "candidate reporting only; not an accuracy or correctness threshold",
            "fraction_at_or_above": float(np.mean(distance_mm >= reporting_threshold_mm)),
            "bands": disagreement_bands(z, distance_mm, reporting_threshold_mm),
        },
        "ct_review_candidates": review_candidates(
            z,
            ours_xy,
            reference_xy,
            distances,
            voxel_size_um,
            candidate_count,
            candidate_separation_z,
        ),
    }
    return metrics, rows


def compare_all(
    ours_dir: Path,
    reference_dir: Path,
    scrolls: Iterable[str],
    **kwargs: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    summaries, dense_rows = [], []
    for scroll in scrolls:
        ours_path = ours_dir / f"{scroll}_umbilicus.json"
        reference_path = reference_dir / f"{scroll}_umbilicus.json"
        summary, rows = compare_one(scroll, ours_path, reference_path, **kwargs)
        summaries.append(summary)
        dense_rows.extend(rows)
    return summaries, dense_rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    require(bool(rows), "refusing to write an empty CSV")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ours-dir", type=Path, default=root / "manual")
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--ours-path", type=Path, help="Single-curve override; requires exactly one --scroll.")
    parser.add_argument("--reference-path", type=Path, help="Single reference override; requires exactly one --scroll.")
    parser.add_argument("--output", type=Path, default=root / "audit" / "comparison_summary.json")
    parser.add_argument("--dense-csv", type=Path)
    parser.add_argument("--scroll", action="append", choices=sorted(SCROLLS))
    parser.add_argument("--sample-step-z", type=int, default=1)
    parser.add_argument("--candidate-count", type=int, default=3)
    parser.add_argument("--candidate-separation-z", type=int, default=750)
    parser.add_argument("--reporting-threshold-mm", type=float, default=1.81)
    parser.add_argument("--ours-revision", default="unspecified")
    parser.add_argument("--reference-revision", default="unspecified")
    parser.add_argument("--reference-url", default="unspecified")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    scrolls = tuple(args.scroll or DEFAULT_SCROLLS)
    compare_kwargs = {
        "sample_step_z": args.sample_step_z,
        "candidate_count": args.candidate_count,
        "candidate_separation_z": args.candidate_separation_z,
        "reporting_threshold_mm": args.reporting_threshold_mm,
    }
    if args.ours_path is not None or args.reference_path is not None:
        require(len(scrolls) == 1, "single-curve path overrides require exactly one --scroll")
        scroll = scrolls[0]
        summary, dense_rows = compare_one(
            scroll,
            args.ours_path or args.ours_dir / f"{scroll}_umbilicus.json",
            args.reference_path or args.reference_dir / f"{scroll}_umbilicus.json",
            **compare_kwargs,
        )
        summaries = [summary]
    else:
        summaries, dense_rows = compare_all(
            args.ours_dir,
            args.reference_dir,
            scrolls,
            **compare_kwargs,
        )
    result = {
        "format": FORMAT,
        "claim_boundary": (
            "Same-z lateral disagreement between independent polylines. Distance alone does not "
            "identify the correct annotation; every proposed correction requires exact-CT review."
        ),
        "coordinate_convention": "Villa control_points x/y/z at level 0; linear interpolation in z",
        "ours_revision": args.ours_revision,
        "reference_revision": args.reference_revision,
        "reference_url": args.reference_url,
        "scroll_count": len(summaries),
        "scrolls": summaries,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.dense_csv:
        write_csv(args.dense_csv, dense_rows)
    print(f"Compared {len(summaries)} independent curve pairs: {args.output}")
    if args.dense_csv:
        print(f"Wrote {len(dense_rows)} same-z samples: {args.dense_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
