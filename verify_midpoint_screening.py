#!/usr/bin/env python3
"""Verify curve-bound assisted midpoint screening receipt metadata."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from compare_independent_curves import load_curve, sha256


class ScreeningError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ScreeningError(message)


def repository_path(root: Path, value: str) -> Path:
    candidate = Path(value)
    require(not candidate.is_absolute(), f"manifest path must be repository-relative: {value}")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as error:
        raise ScreeningError(f"manifest path escapes repository: {value}") from error
    require(resolved.is_file(), f"missing manifest input: {value}")
    return resolved


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"expected JSON object: {path}")
    return value


def midpoint_segment_number(item: dict, *, orthogonal: bool) -> int:
    index = item.get("segment_index")
    require(isinstance(index, int) and index >= 0, "segment_index must be a non-negative integer")
    number = index + 1
    if orthogonal:
        require(item.get("segment_number") == number, "segment number/index mismatch")
    return number


def verify_midpoint_geometry(item: dict, number: int, points) -> None:
    require(1 <= number < len(points), f"segment {number} is outside the curve")
    start = points[number - 1]
    end = points[number]
    midpoint = item.get("exact_mid_xyz")
    require(isinstance(midpoint, list) and len(midpoint) == 3, f"segment {number}: bad midpoint")
    require(all(isinstance(value, (int, float)) and math.isfinite(value) for value in midpoint),
            f"segment {number}: non-finite midpoint")
    z = float(midpoint[2])
    require(float(start[2]) <= z <= float(end[2]), f"segment {number}: midpoint z outside controls")
    fraction = (z - float(start[2])) / (float(end[2]) - float(start[2]))
    expected = start + fraction * (end - start)
    require(
        all(abs(float(actual) - float(want)) <= 1e-6 for actual, want in zip(midpoint, expected)),
        f"segment {number}: midpoint is not on the bound curve interval",
    )
    if "start_xyz" in item:
        require(all(abs(float(a) - float(b)) <= 1e-6 for a, b in zip(item["start_xyz"], start)),
                f"segment {number}: start control mismatch")
    if "end_xyz" in item:
        require(all(abs(float(a) - float(b)) <= 1e-6 for a, b in zip(item["end_xyz"], end)),
                f"segment {number}: end control mismatch")


def verify_evidence_manifest(data: dict, scroll: str, curve_hash: str, points) -> set[int]:
    require(data.get("scroll") == scroll, f"{scroll}: evidence scroll mismatch")
    require(data.get("curve", {}).get("sha256") == curve_hash, f"{scroll}: evidence curve mismatch")
    require(isinstance(data.get("source_stream"), str) and data["source_stream"].startswith("https://"),
            f"{scroll}: invalid source stream")
    require(data.get("failed_source_chunks") == 0, f"{scroll}: evidence has failed source chunks")
    missing = data.get("missing_source_chunks")
    require(isinstance(missing, int) and missing >= 0, f"{scroll}: invalid missing chunk count")
    segments = data.get("segments")
    require(isinstance(segments, list), f"{scroll}: evidence segments must be a list")
    orthogonal = data.get("format") == "umbilicus-midpoint-orthogonal-review-v1"
    require(
        orthogonal or data.get("format") == "umbilicus-midpoint-density-audit-v1",
        f"{scroll}: unsupported evidence format",
    )
    if orthogonal:
        require(data.get("render", {}).get("strict_chunk_fetch") is True,
                f"{scroll}: orthogonal renderer was not fail-closed")
    numbers = []
    for item in segments:
        require(isinstance(item, dict), f"{scroll}: segment record must be an object")
        number = midpoint_segment_number(item, orthogonal=orthogonal)
        verify_midpoint_geometry(item, number, points)
        if orthogonal:
            planes = item.get("planes")
            require(isinstance(planes, list) and len(planes) == 2,
                    f"{scroll} segment {number}: expected XZ and YZ planes")
            require({plane.get("axis") for plane in planes} == {"x", "y"},
                    f"{scroll} segment {number}: orthogonal axes are incomplete")
            for plane in planes:
                require(plane.get("isotropic_display") is True,
                        f"{scroll} segment {number}: distorted orthogonal display")
                bounds = plane.get("other_level_range")
                trajectory = plane.get("candidate_other_level_range")
                require(isinstance(bounds, list) and len(bounds) == 2 and bounds[1] > bounds[0],
                        f"{scroll} segment {number}: invalid orthogonal bounds")
                require(isinstance(trajectory, list) and len(trajectory) == 2,
                        f"{scroll} segment {number}: missing candidate range")
                require(float(trajectory[0]) >= float(bounds[0]) and
                        float(trajectory[1]) <= float(bounds[1]) - 1,
                        f"{scroll} segment {number}: candidate trajectory is clipped")
                display = plane.get("display_size_pixels")
                require(isinstance(display, list) and len(display) == 2 and
                        all(isinstance(value, int) and value > 0 for value in display),
                        f"{scroll} segment {number}: invalid display size")
        numbers.append(number)
    require(numbers == sorted(set(numbers)), f"{scroll}: evidence segment numbers must be sorted and unique")
    if not orthogonal:
        require(data.get("selected_segment_numbers") == numbers,
                f"{scroll}: selected segment list does not match records")
    return set(numbers)


def verify_summary(summary_path: Path, root: Path) -> tuple[int, int]:
    summary = load_json(summary_path)
    require(summary.get("format") == "umbilicus-assisted-midpoint-screen-v1", "unexpected summary format")
    require("not expert acceptance" in summary.get("claim_boundary", ""), "missing claim boundary")
    scrolls = summary.get("scrolls")
    require(isinstance(scrolls, dict) and bool(scrolls), "summary must contain scroll records")
    checked_intervals = 0
    for scroll, record in sorted(scrolls.items()):
        curve_record = record.get("curve", {})
        curve_path = repository_path(root, curve_record.get("path", ""))
        curve_hash = sha256(curve_path)
        require(curve_record.get("sha256") == curve_hash, f"{scroll}: curve hash mismatch")
        points = load_curve(curve_path)
        interval_count = len(points) - 1
        require(record.get("interval_count") == interval_count, f"{scroll}: interval count mismatch")

        groups = {}
        for key in ("keep_linear", "add_control", "unresolved"):
            values = record.get(key)
            require(isinstance(values, list), f"{scroll}: {key} must be a list")
            require(values == sorted(set(values)), f"{scroll}: {key} must be sorted and unique")
            groups[key] = set(values)
        require(not (groups["keep_linear"] & groups["add_control"]), f"{scroll}: overlapping decisions")
        require(not (groups["keep_linear"] & groups["unresolved"]), f"{scroll}: overlapping decisions")
        require(not (groups["add_control"] & groups["unresolved"]), f"{scroll}: overlapping decisions")
        require(
            groups["keep_linear"] | groups["add_control"] | groups["unresolved"]
            == set(range(1, interval_count + 1)),
            f"{scroll}: decisions do not partition every interval",
        )

        full_path = repository_path(root, record.get("full_midpoint_manifest", ""))
        full = load_json(full_path)
        require(full.get("format") == "umbilicus-midpoint-density-audit-v1", f"{scroll}: bad full manifest")
        require(full.get("scroll") == scroll, f"{scroll}: full manifest scroll mismatch")
        require(full.get("curve", {}).get("sha256") == curve_hash, f"{scroll}: full manifest curve mismatch")
        full_numbers = verify_evidence_manifest(full, scroll, curve_hash, points)
        require(full_numbers == set(range(1, interval_count + 1)), f"{scroll}: full manifest is incomplete")

        orthogonal_coverage: set[int] = set()
        evidence_paths = record.get("escalation_manifests")
        require(isinstance(evidence_paths, list), f"{scroll}: escalation_manifests must be a list")
        require(evidence_paths == list(dict.fromkeys(evidence_paths)), f"{scroll}: duplicate evidence manifests")
        for value in evidence_paths:
            evidence = load_json(repository_path(root, value))
            require(evidence.get("source_stream") == full.get("source_stream"),
                    f"{scroll}: evidence source stream mismatch: {value}")
            evidence_numbers = verify_evidence_manifest(evidence, scroll, curve_hash, points)
            if evidence.get("format") == "umbilicus-midpoint-orthogonal-review-v1":
                orthogonal_coverage.update(evidence_numbers)
        require(
            groups["add_control"] | groups["unresolved"] <= orthogonal_coverage,
            f"{scroll}: every non-keep interval must have orthogonal evidence",
        )
        checked_intervals += interval_count
    return len(scrolls), checked_intervals


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "summary",
        type=Path,
        nargs="?",
        default=root / "audit" / "midpoint_density" / "assisted_screening_summary.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent
    scroll_count, interval_count = verify_summary(args.summary, root)
    print(f"PASS: {scroll_count} curves, {interval_count} midpoint intervals, curve-bound receipt metadata complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
