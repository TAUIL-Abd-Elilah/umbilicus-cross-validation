#!/usr/bin/env python3
"""Approve one human-reviewed Khartes umbilicus candidate for release.

This tool does not judge CT imagery.  It enforces the mechanical boundary
between a working candidate and a release-shaped manual curve: exact paths,
Villa JSON schema, eligible scroll/range/stream, non-identity with either
automatic initializer, explicit human QC, screenshot evidence, hashes, and
no-overwrite publication into ``manual/``.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Iterable

from PIL import Image, UnidentifiedImageError

from scrolls import SCROLLS


OPEN_DATA_ROOT = "https://vesuvius-challenge-open-data.s3.amazonaws.com"

# PHerc0826 is intentionally absent.  The agent/operator queue contains only
# the ten scrolls whose manual curves are missing.
ELIGIBLE: dict[str, dict[str, Any]] = {
    "PHerc0191": {"bracket": (960, 18976), "ct": "20250821151635-9.362um-1.2m-113keV-masked.zarr"},
    "PHerc0257": {"bracket": (960, 18368), "ct": "20250821151750-9.362um-1.2m-113keV-masked.zarr"},
    "PHerc0268": {"bracket": (384, 14816), "ct": "20251110183117-8.640um-1.2m-116keV-masked.zarr"},
    "PHerc0358": {"bracket": (384, 14720), "ct": "20250821151737-9.362um-1.2m-113keV-masked.zarr"},
    "PHerc0800": {"bracket": (0, 24288), "ct": "20250521135224-8.640um-1.2m-116keV-masked.zarr"},
    "PHerc0813": {"bracket": (1728, 16992), "ct": "20250821151723-9.362um-1.2m-113keV-masked.zarr"},
    "PHerc1203": {"bracket": (960, 18976), "ct": "20250820131727-9.362um-1.2m-113keV-masked.zarr"},
    "PHerc1218": {"bracket": (0, 23232), "ct": "20250521120456-8.640um-1.2m-116keV-masked.zarr"},
    "PHerc1447": {"bracket": (0, 24288), "ct": "20250521151220-8.640um-1.2m-116keV-masked.zarr"},
    "PHerc1545": {"bracket": (1088, 20960), "ct": "20250821151648-9.362um-1.2m-113keV-masked.zarr"},
}

ALLOWED_DATA_LICENSES = ("CC-BY-4.0", "CC-BY-NC-4.0", "CC0-1.0")
SCREENSHOT_SUFFIXES = {".png", ".jpg", ".jpeg"}
SCREENSHOT_FORMATS = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG"}
REQUIRED_SCREENSHOT_ROLES = {"start", "middle", "end"}
MIN_SCREENSHOT_DIMENSION = 256


class ApprovalError(ValueError):
    """Raised when a manual candidate is not mechanically release-ready."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def expected_ct_url(scroll: str) -> str:
    entry = ELIGIBLE[scroll]
    return f"{OPEN_DATA_ROOT}/{scroll}/volumes/{entry['ct']}"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ApprovalError(message)


def load_object(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    require(path.is_file(), f"missing {label}: {path}")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ApprovalError(f"invalid JSON in {label}: {path}") from error
    require(isinstance(value, dict), f"{label} root must be an object")
    return value, raw


def coordinates(value: dict[str, Any], label: str) -> list[tuple[int, int, int]]:
    points = value.get("control_points")
    require(isinstance(points, list), f"{label}.control_points must be a list")
    result: list[tuple[int, int, int]] = []
    for index, point in enumerate(points):
        require(isinstance(point, dict), f"{label} point {index} must be an object")
        xyz: list[int] = []
        for field in ("x", "y", "z"):
            item = point.get(field)
            require(
                isinstance(item, int) and not isinstance(item, bool),
                f"{label} point {index}.{field} must be an integer",
            )
            xyz.append(item)
        result.append((xyz[0], xyz[1], xyz[2]))
    return result


def sorted_coordinates(value: dict[str, Any], label: str) -> list[tuple[int, int, int]]:
    return sorted(coordinates(value, label), key=lambda point: point[2])


def parse_qc_time(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ApprovalError("--qc-time must be an ISO-8601 timestamp") from error
    require(parsed.tzinfo is not None, "--qc-time must include a timezone")
    parsed_utc = parsed.astimezone(timezone.utc)
    require(parsed_utc <= datetime.now(timezone.utc), "--qc-time cannot be in the future")
    return parsed_utc.isoformat()


def screenshot_role(path: Path) -> str | None:
    match = re.search(
        r"(?:^|[_\-.])(start|middle|end)(?:$|[_\-.])",
        path.stem.lower(),
    )
    return match.group(1) if match else None


def screenshot_z(path: Path) -> int | None:
    match = re.search(r"(?:^|[_\-.])z(\d+)(?:$|[_\-.])", path.stem.lower())
    return int(match.group(1)) if match else None


def decoded_image(path: Path) -> tuple[str, int, int]:
    try:
        with Image.open(path) as image:
            image_format = image.format
            width, height = image.size
            image.verify()
    except (OSError, SyntaxError, UnidentifiedImageError) as error:
        raise ApprovalError(f"screenshot is not a decodable image: {path}") from error
    require(image_format is not None, f"screenshot has no detected image format: {path}")
    expected_format = SCREENSHOT_FORMATS[path.suffix.lower()]
    require(
        image_format.upper() == expected_format,
        f"screenshot extension/format mismatch: {path}",
    )
    require(
        width >= MIN_SCREENSHOT_DIMENSION and height >= MIN_SCREENSHOT_DIMENSION,
        f"screenshot must be at least {MIN_SCREENSHOT_DIMENSION}x{MIN_SCREENSHOT_DIMENSION}: {path}",
    )
    return image_format.upper(), width, height


def validate_screenshots(
    root: Path, scroll: str, screenshots: Iterable[Path]
) -> list[dict[str, Any]]:
    paths = [path.resolve() for path in screenshots]
    require(len(paths) >= 3, "at least three screenshots are required (start/middle/end)")
    require(len(set(paths)) == len(paths), "screenshot paths must be unique")
    screenshot_root = (root / "manual" / "screenshots" / scroll).resolve()
    rows: list[dict[str, Any]] = []
    found_roles: set[str] = set()
    for path in paths:
        require(path.is_relative_to(screenshot_root), f"screenshot is outside {screenshot_root}: {path}")
        require(path.is_file(), f"missing screenshot: {path}")
        require(path.suffix.lower() in SCREENSHOT_SUFFIXES, f"unsupported screenshot type: {path}")
        require(scroll.lower() in path.name.lower(), f"screenshot filename must contain {scroll}: {path.name}")
        role = screenshot_role(path)
        if role is not None:
            found_roles.add(role)
        image_format, width, height = decoded_image(path)
        z_value = screenshot_z(path)
        require(
            z_value is not None,
            f"screenshot filename must contain a z<integer> token: {path.name}",
        )
        require(
            0 <= z_value < SCROLLS[scroll]["shape"][0],
            f"screenshot z token is outside the CT volume: {path.name}",
        )
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "role": role or "additional",
                "z": z_value,
                "format": image_format,
                "width": width,
                "height": height,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    missing_roles = sorted(REQUIRED_SCREENSHOT_ROLES - found_roles)
    require(
        not missing_roles,
        "screenshots must identify start, middle, and end in their filenames; "
        f"missing: {', '.join(missing_roles)}",
    )
    required_rows = {role: next(row for row in rows if row["role"] == role) for role in REQUIRED_SCREENSHOT_ROLES}
    require(
        required_rows["start"]["z"] < required_rows["middle"]["z"] < required_rows["end"]["z"],
        "start/middle/end screenshot z tokens must be strictly increasing",
    )
    require(
        len({required_rows[role]["sha256"] for role in REQUIRED_SCREENSHOT_ROLES}) == 3,
        "start/middle/end screenshots must be three distinct images",
    )
    return rows


def _write_temp(parent: Path, prefix: str, payload: bytes) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=prefix, suffix=".tmp", dir=parent)
    path = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def approve(
    *,
    root: Path,
    scroll: str,
    candidate: Path,
    reviewer: str,
    qc_time: str,
    ct_url: str,
    data_license: str,
    screenshots: Iterable[Path],
    qc_checked: bool,
) -> tuple[Path, Path]:
    root = root.resolve(strict=True)
    require(scroll in ELIGIBLE, f"scroll is not in the eligible-ten manual queue: {scroll}")
    require(qc_checked is True, "approval requires explicit --qc-checked")
    reviewer = reviewer.strip()
    require(len(reviewer) >= 2, "--reviewer must identify the human reviewer")
    qc_time_utc = parse_qc_time(qc_time)
    require(data_license in ALLOWED_DATA_LICENSES, "unsupported or missing --data-license")
    expected_url = expected_ct_url(scroll)
    require(ct_url == expected_url, f"CT URL mismatch; expected {expected_url}")

    expected_candidate = (
        root / "manual" / "candidates" / f"{scroll}_umbilicus.candidate.json"
    ).resolve()
    candidate = candidate.resolve()
    require(candidate == expected_candidate, f"candidate must use the exact path {expected_candidate}")
    candidate_value, candidate_bytes = load_object(candidate, "manual candidate")
    candidate_in_file_order = coordinates(candidate_value, "manual candidate")
    candidate_coordinates = sorted(candidate_in_file_order, key=lambda point: point[2])
    require(24 <= len(candidate_coordinates) <= 40, "manual candidate must contain 24-40 controls")
    file_z_values = [point[2] for point in candidate_in_file_order]
    require(
        file_z_values == sorted(file_z_values),
        "manual candidate control points must be ordered by increasing z",
    )
    z_values = [point[2] for point in candidate_coordinates]
    require(len(set(z_values)) == len(z_values), "manual candidate z coordinates must be unique")
    bracket_min, bracket_max = ELIGIBLE[scroll]["bracket"]
    require(
        min(z_values) >= bracket_min and max(z_values) <= bracket_max,
        f"manual candidate z range must stay within {bracket_min}-{bracket_max}",
    )
    span = bracket_max - bracket_min
    require(
        min(z_values) <= bracket_min + 0.10 * span
        and max(z_values) >= bracket_max - 0.10 * span,
        "manual candidate must cover at least the central 80% of the useful z bracket",
    )
    volume_shape = tuple(SCROLLS[scroll]["shape"])
    require(
        SCROLLS[scroll]["ct"] == ELIGIBLE[scroll]["ct"],
        f"internal CT metadata mismatch for {scroll}",
    )
    for index, (x, y, z) in enumerate(candidate_in_file_order):
        require(
            0 <= x < volume_shape[2],
            f"manual candidate point {index}.x is outside volume bounds 0-{volume_shape[2] - 1}",
        )
        require(
            0 <= y < volume_shape[1],
            f"manual candidate point {index}.y is outside volume bounds 0-{volume_shape[1] - 1}",
        )
        require(
            0 <= z < volume_shape[0],
            f"manual candidate point {index}.z is outside volume bounds 0-{volume_shape[0] - 1}",
        )

    automatic_rows: list[dict[str, Any]] = []
    for kind in ("seed", "estimated"):
        automatic_path = root / "seeds" / f"{scroll}_umbilicus_{kind}.json"
        automatic_value, _ = load_object(automatic_path, f"automatic {kind}")
        automatic_coordinates = sorted_coordinates(automatic_value, f"automatic {kind}")
        exact_match = candidate_coordinates == automatic_coordinates
        require(not exact_match, f"candidate is an untouched automatic {kind} curve")
        automatic_rows.append(
            {
                "kind": kind,
                "path": automatic_path.relative_to(root).as_posix(),
                "sha256": sha256_file(automatic_path),
                "exact_coordinate_match": False,
            }
        )

    screenshot_rows = validate_screenshots(root, scroll, screenshots)
    final_path = root / "manual" / f"{scroll}_umbilicus.json"
    manifest_path = root / "manual" / "manifests" / f"{scroll}_qc.json"
    require(not final_path.exists(), f"refusing to overwrite approved curve: {final_path}")
    require(not manifest_path.exists(), f"refusing to overwrite QC manifest: {manifest_path}")

    final_sha = sha256_bytes(candidate_bytes)
    manifest = {
        "format": "villa-manual-umbilicus-qc-v2",
        "scroll": scroll,
        "qc_checked": True,
        "reviewer": reviewer,
        "qc_completed_at_utc": qc_time_utc,
        "approved_at_utc": datetime.now(timezone.utc).isoformat(),
        "ct_url": expected_url,
        "data_license": data_license,
        "candidate": {
            "path": candidate.relative_to(root).as_posix(),
            "sha256": final_sha,
            "bytes": len(candidate_bytes),
        },
        "approved_curve": {
            "path": final_path.relative_to(root).as_posix(),
            "sha256": final_sha,
            "bytes": len(candidate_bytes),
            "control_count": len(candidate_coordinates),
            "x_min": min(point[0] for point in candidate_coordinates),
            "x_max": max(point[0] for point in candidate_coordinates),
            "y_min": min(point[1] for point in candidate_coordinates),
            "y_max": max(point[1] for point in candidate_coordinates),
            "z_min": min(z_values),
            "z_max": max(z_values),
            "volume_shape_zyx": list(volume_shape),
        },
        "automatic_initializers": automatic_rows,
        "screenshots": screenshot_rows,
        "claim_boundary": (
            "Human-reviewed fit-ready approximation; not exact ground truth, "
            "Kaggle hidden-test evidence, or a letter-reading result."
        ),
        "approval_tool_sha256": sha256_file(Path(__file__).resolve()),
    }
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")

    final_temp = _write_temp(final_path.parent, f".{scroll}.curve.", candidate_bytes)
    manifest_temp = _write_temp(manifest_path.parent, f".{scroll}.manifest.", manifest_bytes)
    installed_manifest = False
    try:
        # Install the manifest first. A crash can leave a manifest without a
        # curve, which is visibly incomplete; it must never leave a final-looking
        # curve without its approval record.
        manifest_temp.rename(manifest_path)
        installed_manifest = True
        final_temp.rename(final_path)
    except BaseException:
        final_temp.unlink(missing_ok=True)
        manifest_temp.unlink(missing_ok=True)
        if installed_manifest and not final_path.exists():
            manifest_path.unlink(missing_ok=True)
        raise

    require(sha256_file(final_path) == final_sha, "approved curve hash changed during installation")
    require(sha256_file(manifest_path) == sha256_bytes(manifest_bytes), "QC manifest hash changed")
    return final_path, manifest_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=root)
    parser.add_argument("--scroll", required=True, choices=sorted(ELIGIBLE))
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--qc-time", required=True, help="ISO-8601 timestamp with timezone")
    parser.add_argument("--ct-url", required=True)
    parser.add_argument("--data-license", required=True, choices=ALLOWED_DATA_LICENSES)
    parser.add_argument("--screenshot", type=Path, action="append", required=True)
    parser.add_argument("--qc-checked", action="store_true")
    args = parser.parse_args(argv)
    if args.candidate is None:
        args.candidate = (
            args.root / "manual" / "candidates" / f"{args.scroll}_umbilicus.candidate.json"
        )
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        final_path, manifest_path = approve(
            root=args.root,
            scroll=args.scroll,
            candidate=args.candidate,
            reviewer=args.reviewer,
            qc_time=args.qc_time,
            ct_url=args.ct_url,
            data_license=args.data_license,
            screenshots=args.screenshot,
            qc_checked=args.qc_checked,
        )
    except (ApprovalError, OSError) as error:
        print(f"approve_manual_curve.py: {error}", file=os.sys.stderr)
        return 1
    print(f"Approved curve: {final_path}")
    print(f"QC manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
