#!/usr/bin/env python3
"""Verify the complete ten-scroll human umbilicus release, read-only by default.

This is deliberately not an estimator or an image judge.  It verifies that every
eligible manual curve passed the v2 per-curve approval contract, that all files and
screenshots still match their hash-bound manifests, and that Villa's real Spiral
loader consumes every curve with the expected X/Y/Z convention.  With
``--write-manifest`` it installs one no-overwrite aggregate manifest, but only after
the entire ten-scroll set passes.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import ModuleType
from typing import Any

import numpy as np

import approve_manual_curve as approval
from scrolls import SCROLLS


RELEASE_FORMAT = "villa-manual-umbilicus-release-v1"
QC_FORMAT = "villa-manual-umbilicus-qc-v2"
RELEASE_FILENAME = "release_manifest.json"


class ReleaseError(ValueError):
    """Raised when the manual ten-scroll release is incomplete or inconsistent."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReleaseError(message)


def load_object(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    require(path.is_file(), f"missing {label}: {path}")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReleaseError(f"invalid JSON in {label}: {path}") from error
    require(isinstance(value, dict), f"{label} root must be an object")
    return value, raw


def parse_time(value: Any, label: str) -> datetime:
    require(isinstance(value, str), f"{label} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ReleaseError(f"{label} must be an ISO-8601 timestamp") from error
    require(parsed.tzinfo is not None, f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


def relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def external_display_path(root: Path, path: Path) -> str:
    try:
        return os.path.relpath(path, root).replace(os.sep, "/")
    except ValueError:
        # Windows cannot express a relative path across drive letters.
        return path.resolve().as_posix()


def validate_curve_geometry(
    scroll: str, value: dict[str, Any], label: str
) -> tuple[list[tuple[int, int, int]], dict[str, Any]]:
    points_in_order = approval.coordinates(value, label)
    require(24 <= len(points_in_order) <= 40, f"{label} must contain 24-40 controls")
    z_values = [point[2] for point in points_in_order]
    require(z_values == sorted(z_values), f"{label} controls are not ordered by increasing z")
    require(len(set(z_values)) == len(z_values), f"{label} z coordinates are not unique")

    bracket_min, bracket_max = approval.ELIGIBLE[scroll]["bracket"]
    require(
        min(z_values) >= bracket_min and max(z_values) <= bracket_max,
        f"{label} z range is outside {bracket_min}-{bracket_max}",
    )
    span = bracket_max - bracket_min
    require(
        min(z_values) <= bracket_min + 0.10 * span
        and max(z_values) >= bracket_max - 0.10 * span,
        f"{label} does not cover the central 80% of the useful z bracket",
    )

    shape = tuple(SCROLLS[scroll]["shape"])
    require(
        SCROLLS[scroll]["ct"] == approval.ELIGIBLE[scroll]["ct"],
        f"internal CT metadata mismatch for {scroll}",
    )
    for index, (x, y, z) in enumerate(points_in_order):
        require(0 <= x < shape[2], f"{label} point {index}.x is outside the CT volume")
        require(0 <= y < shape[1], f"{label} point {index}.y is outside the CT volume")
        require(0 <= z < shape[0], f"{label} point {index}.z is outside the CT volume")

    metadata = {
        "control_count": len(points_in_order),
        "x_min": min(point[0] for point in points_in_order),
        "x_max": max(point[0] for point in points_in_order),
        "y_min": min(point[1] for point in points_in_order),
        "y_max": max(point[1] for point in points_in_order),
        "z_min": min(z_values),
        "z_max": max(z_values),
        "volume_shape_zyx": list(shape),
    }
    return points_in_order, metadata


def load_villa_loader(path: Path) -> ModuleType:
    require(path.is_file(), f"missing Villa Spiral loader: {path}")
    spec = importlib.util.spec_from_file_location("villa_umbilicus_release_loader", path)
    require(spec is not None and spec.loader is not None, f"cannot import Villa loader: {path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as error:
        raise ReleaseError(f"Villa loader import failed: {path}: {error}") from error
    require(
        callable(getattr(module, "json_umbilicus_z_to_yx", None)),
        "Villa loader lacks json_umbilicus_z_to_yx",
    )
    return module


def smoke_villa_loader(module: ModuleType, curve: Path, points: list[tuple[int, int, int]]) -> None:
    try:
        interpolator = module.json_umbilicus_z_to_yx(str(curve))
        z_values = np.asarray([point[2] for point in points], dtype=np.float32)
        observed = np.asarray(interpolator(z_values))
    except Exception as error:
        raise ReleaseError(f"Villa loader rejected {curve}: {error}") from error
    expected = np.asarray([(point[1], point[0]) for point in points], dtype=np.float32)
    require(observed.shape == expected.shape, f"Villa loader returned wrong shape for {curve}")
    require(np.isfinite(observed).all(), f"Villa loader returned non-finite values for {curve}")
    require(
        np.allclose(observed, expected, rtol=0.0, atol=1e-3),
        f"Villa loader changed canonical Y/X controls for {curve}",
    )


def expected_initializer_rows(root: Path, scroll: str, points: list[tuple[int, int, int]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sorted_points = sorted(points, key=lambda point: point[2])
    for kind in ("seed", "estimated"):
        path = root / "seeds" / f"{scroll}_umbilicus_{kind}.json"
        value, _ = load_object(path, f"{scroll} automatic {kind}")
        automatic = approval.sorted_coordinates(value, f"{scroll} automatic {kind}")
        require(sorted_points != automatic, f"{scroll} final curve is an untouched automatic {kind}")
        rows.append(
            {
                "kind": kind,
                "path": relative(root, path),
                "sha256": approval.sha256_file(path),
                "exact_coordinate_match": False,
            }
        )
    return rows


def validate_one(
    root: Path,
    scroll: str,
    villa_module: ModuleType,
    approval_tool_sha256: str,
) -> dict[str, Any]:
    candidate = root / "manual" / "candidates" / f"{scroll}_umbilicus.candidate.json"
    final = root / "manual" / f"{scroll}_umbilicus.json"
    manifest_path = root / "manual" / "manifests" / f"{scroll}_qc.json"

    candidate_value, candidate_bytes = load_object(candidate, f"{scroll} candidate")
    final_value, final_bytes = load_object(final, f"{scroll} approved curve")
    manifest, manifest_bytes = load_object(manifest_path, f"{scroll} QC manifest")
    require(candidate_bytes == final_bytes, f"{scroll} approved curve no longer matches its candidate")
    require(candidate_value == final_value, f"{scroll} candidate/final JSON values differ")

    points, geometry = validate_curve_geometry(scroll, final_value, f"{scroll} approved curve")
    initializer_rows = expected_initializer_rows(root, scroll, points)

    require(manifest.get("format") == QC_FORMAT, f"{scroll} QC manifest is not {QC_FORMAT}")
    require(manifest.get("scroll") == scroll, f"{scroll} QC manifest scroll mismatch")
    require(manifest.get("qc_checked") is True, f"{scroll} QC manifest is not human-approved")
    reviewer = manifest.get("reviewer")
    require(isinstance(reviewer, str) and len(reviewer.strip()) >= 2, f"{scroll} reviewer is missing")
    qc_time = parse_time(manifest.get("qc_completed_at_utc"), f"{scroll} QC time")
    approved_time = parse_time(manifest.get("approved_at_utc"), f"{scroll} approval time")
    require(approved_time >= qc_time, f"{scroll} approval predates its QC completion")
    require(
        manifest.get("ct_url") == approval.expected_ct_url(scroll),
        f"{scroll} QC manifest CT URL mismatch",
    )
    data_license = manifest.get("data_license")
    require(data_license in approval.ALLOWED_DATA_LICENSES, f"{scroll} data licence is invalid")
    require(
        manifest.get("approval_tool_sha256") == approval_tool_sha256,
        f"{scroll} was approved by a different/stale approval tool",
    )

    final_sha = approval.sha256_bytes(final_bytes)
    expected_candidate = {
        "path": relative(root, candidate),
        "sha256": final_sha,
        "bytes": len(candidate_bytes),
    }
    expected_approved = {
        "path": relative(root, final),
        "sha256": final_sha,
        "bytes": len(final_bytes),
        **geometry,
    }
    require(manifest.get("candidate") == expected_candidate, f"{scroll} candidate manifest row mismatch")
    require(manifest.get("approved_curve") == expected_approved, f"{scroll} approved manifest row mismatch")
    require(
        manifest.get("automatic_initializers") == initializer_rows,
        f"{scroll} automatic-initializer provenance mismatch",
    )

    screenshot_rows = manifest.get("screenshots")
    require(isinstance(screenshot_rows, list), f"{scroll} screenshot manifest must be a list")
    screenshot_paths: list[Path] = []
    for index, row in enumerate(screenshot_rows):
        require(isinstance(row, dict), f"{scroll} screenshot row {index} must be an object")
        item = row.get("path")
        require(isinstance(item, str), f"{scroll} screenshot row {index} has no path")
        screenshot_paths.append(root / Path(item))
    recomputed_screenshots = approval.validate_screenshots(root, scroll, screenshot_paths)
    require(recomputed_screenshots == screenshot_rows, f"{scroll} screenshot evidence changed")

    screenshot_root = root / "manual" / "screenshots" / scroll
    actual_images = {
        relative(root, path)
        for path in screenshot_root.rglob("*")
        if path.is_file() and path.suffix.lower() in approval.SCREENSHOT_SUFFIXES
    }
    declared_images = {row["path"] for row in screenshot_rows}
    require(
        actual_images == declared_images,
        f"{scroll} screenshot directory contains undeclared or missing evidence files",
    )

    smoke_villa_loader(villa_module, final, points)
    return {
        "scroll": scroll,
        "approved_curve": expected_approved,
        "qc_manifest": {
            "path": relative(root, manifest_path),
            "sha256": approval.sha256_bytes(manifest_bytes),
            "bytes": len(manifest_bytes),
        },
        "reviewer": reviewer.strip(),
        "qc_completed_at_utc": qc_time.isoformat(),
        "approved_at_utc": approved_time.isoformat(),
        "data_license": data_license,
        "ct_url": approval.expected_ct_url(scroll),
        "screenshots": screenshot_rows,
    }


def content_digest(rows: list[dict[str, Any]]) -> str:
    content = [
        {
            "scroll": row["scroll"],
            "curve_path": row["approved_curve"]["path"],
            "curve_sha256": row["approved_curve"]["sha256"],
            "curve_bytes": row["approved_curve"]["bytes"],
            "manifest_path": row["qc_manifest"]["path"],
            "manifest_sha256": row["qc_manifest"]["sha256"],
            "manifest_bytes": row["qc_manifest"]["bytes"],
        }
        for row in rows
    ]
    payload = json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def verify_release(root: Path, villa_loader: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    approval_tool = (root / "approve_manual_curve.py").resolve()
    verifier_tool = (root / "verify_manual_release.py").resolve()
    require(
        approval_tool.is_file(),
        f"release root lacks approve_manual_curve.py: {approval_tool}",
    )
    require(
        verifier_tool.is_file(),
        f"release root lacks verify_manual_release.py: {verifier_tool}",
    )
    require(
        approval.sha256_file(approval_tool) == approval.sha256_file(Path(approval.__file__).resolve()),
        "release-root approval tool differs from the code executing verification",
    )
    require(
        approval.sha256_file(verifier_tool) == approval.sha256_file(Path(__file__).resolve()),
        "release-root verifier differs from the code executing verification",
    )
    approval_sha = approval.sha256_file(approval_tool)
    villa_loader = villa_loader.resolve(strict=True)
    villa_module = load_villa_loader(villa_loader)

    rows = [
        validate_one(root, scroll, villa_module, approval_sha)
        for scroll in sorted(approval.ELIGIBLE)
    ]
    require(len(rows) == 10, "eligible manual release must contain exactly ten curves")
    curve_hashes = [row["approved_curve"]["sha256"] for row in rows]
    require(len(set(curve_hashes)) == len(curve_hashes), "two scrolls have byte-identical curves")
    licences = sorted({row["data_license"] for row in rows})
    require(len(licences) == 1, "all ten curves must use one coherent data licence")

    result = {
        "format": RELEASE_FORMAT,
        "scope": "ten-new-human-curves",
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "curve_count": len(rows),
        "scrolls": [row["scroll"] for row in rows],
        "data_license": licences[0],
        "release_content_sha256": content_digest(rows),
        "approval_tool": {
            "path": relative(root, approval_tool),
            "sha256": approval_sha,
        },
        "release_verifier": {
            "path": relative(root, verifier_tool),
            "sha256": approval.sha256_file(verifier_tool),
        },
        "villa_loader": {
            "path": external_display_path(root, villa_loader),
            "sha256": approval.sha256_file(villa_loader),
            "function": "json_umbilicus_z_to_yx",
        },
        "entries": rows,
        "claim_boundary": (
            "Ten human-reviewed fit-ready approximations; not exact ground truth, "
            "a complete licensed 13-curve bundle, Kaggle hidden-test evidence, or a letter-reading result."
        ),
    }
    existing_path = root / "manual" / RELEASE_FILENAME
    if existing_path.exists():
        existing, _ = load_object(existing_path, "aggregate release manifest")
        expected = dict(result)
        expected["verified_at_utc"] = existing.get("verified_at_utc")
        require(existing == expected, "aggregate release manifest is stale or tampered")
        return existing
    return result


def write_manifest(root: Path, manifest: dict[str, Any]) -> Path:
    output = root.resolve() / "manual" / RELEASE_FILENAME
    require(not output.exists(), f"refusing to overwrite aggregate release manifest: {output}")
    payload = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".release_manifest.", suffix=".tmp", dir=output.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.rename(output)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    require(approval.sha256_file(output) == approval.sha256_bytes(payload), "release manifest changed")
    return output


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    default_loader = root.parent / "villa" / "volume-cartographer" / "scripts" / "spiral" / "umbilicus.py"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=root)
    parser.add_argument("--villa-loader", type=Path, default=default_loader)
    parser.add_argument("--write-manifest", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        manifest = verify_release(args.root, args.villa_loader)
        if args.write_manifest:
            output = write_manifest(args.root, manifest)
            print(f"Verified ten-curve release: {output}")
        else:
            print(json.dumps(manifest, indent=2, sort_keys=True))
    except (ReleaseError, approval.ApprovalError, OSError) as error:
        print(f"verify_manual_release.py: {error}", file=os.sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
