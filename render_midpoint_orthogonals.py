#!/usr/bin/env python3
"""Render candidate-following XZ/YZ checks for selected midpoint intervals.

These local reviewer packs complement axial midpoint screens. Each longitudinal
plane follows the candidate curve in the complementary coordinate, so the red
line can be checked for continuity through z. The renderer is fail-closed:
validated Zarr zero-fill chunks are recorded, and every other fetch failure
aborts instead of producing a silent black image.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from audit_midpoint_density import (
    BACKGROUND,
    MARKER,
    MUTED,
    TEXT,
    font,
    portable_path,
    segment_rows,
    select_segment_rows,
    selection_slug,
    sha256,
)
from compare_independent_curves import DEFAULT_SCROLLS, interpolate_xy, load_curve
from longitudinal import ChunkCache, curved_plane_along_z
from scrolls import SCROLLS
from slicefetch import open_pyramid, scroll_volume_path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def enhance(array: np.ndarray) -> np.ndarray:
    return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(array)


def candidate_window(
    midpoint: float,
    trajectory: np.ndarray,
    radius: int,
    axis_size: int,
) -> tuple[int, int, bool]:
    """Return an exclusive window containing the complete candidate trajectory."""
    require(radius > 0 and axis_size > 1, "candidate window dimensions must be positive")
    values = np.asarray(trajectory, dtype=float)
    require(values.size > 0 and bool(np.all(np.isfinite(values))), "candidate trajectory is empty or non-finite")
    require(
        float(values.min()) >= 0.0 and float(values.max()) <= axis_size - 1,
        "candidate trajectory leaves the source volume",
    )
    base_lo = int(round(midpoint)) - radius
    base_hi = int(round(midpoint)) + radius
    margin = max(2, int(math.ceil(radius * 0.05)))
    needed_lo = int(math.floor(float(values.min()))) - margin
    needed_hi = int(math.ceil(float(values.max()))) + margin + 1
    lo = max(0, min(base_lo, needed_lo))
    hi = min(axis_size, max(base_hi, needed_hi))
    require(
        float(values.min()) >= lo and float(values.max()) <= hi - 1,
        "candidate trajectory would be clipped by the orthogonal window",
    )
    expanded = lo < max(0, base_lo) or hi > min(axis_size, base_hi)
    return lo, hi, expanded


def resize_isotropic(image: Image.Image, max_size: int) -> Image.Image:
    """Resize without changing the physical z-to-xy aspect ratio."""
    require(max_size > 0, "panel size must be positive")
    width, height = image.size
    require(width > 0 and height > 0, "source panel must be non-empty")
    factor = max_size / max(width, height)
    target = (max(1, round(width * factor)), max(1, round(height * factor)))
    return image.resize(target, Image.Resampling.BICUBIC)


def curve_xy_level(points: np.ndarray, z_level: np.ndarray, scale: int) -> np.ndarray:
    z_full = np.asarray(z_level, dtype=float) * scale
    return interpolate_xy(points, z_full) / scale


def add_scale_bar(image: Image.Image, extent_full: float, voxel_um: float) -> None:
    length_mm = 5.0
    pixels = length_mm * 1000.0 / voxel_um / extent_full * image.width
    x1, y = image.width - 24, image.height - 24
    x0 = x1 - pixels
    draw = ImageDraw.Draw(image)
    draw.rectangle((x0 - 5, y - 19, x1 + 5, y + 12), fill=BACKGROUND)
    draw.line((x0, y, x1, y), fill="white", width=4)
    draw.line((x0, y - 6, x0, y + 6), fill="white", width=3)
    draw.line((x1, y - 6, x1, y + 6), fill="white", width=3)
    draw.text((x0, y - 18), "5 mm", fill="white", font=font(14, True))


def titled(image: Image.Image, title: str, subtitle: str) -> Image.Image:
    bar = 72
    result = Image.new("RGB", (image.width, image.height + bar), BACKGROUND)
    result.paste(image, (0, bar))
    draw = ImageDraw.Draw(result)
    draw.text((10, 8), title, fill=TEXT, font=font(20, True))
    draw.text((10, 38), subtitle, fill=MUTED, font=font(14))
    return result


def overlay_curve(
    image: Image.Image,
    other_level: np.ndarray,
    *,
    other_lo: int,
    other_hi: int,
    midpoint_other: float,
    midpoint_z: float,
    z_lo: int,
    z_hi: int,
) -> None:
    width, height = image.size
    draw = ImageDraw.Draw(image)
    require(other_hi > other_lo and z_hi > z_lo, "orthogonal panel extent must be positive")
    other_span = max(other_hi - other_lo - 1, 1)
    z_span = max(z_hi - z_lo - 1, 1)
    polyline = []
    for row, value in enumerate(other_level):
        x = (float(value) - other_lo) / other_span * (width - 1)
        y = row / max(len(other_level) - 1, 1) * (height - 1)
        polyline.append((x, y))
    if len(polyline) >= 2:
        draw.line(polyline, fill=MARKER, width=4)
    x = (midpoint_other - other_lo) / other_span * (width - 1)
    y = (midpoint_z - z_lo) / z_span * (height - 1)
    radius = 14
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=MARKER, width=5)


def render_plane_pair(
    cache: ChunkCache,
    points: np.ndarray,
    row: dict,
    *,
    axis: str,
    scale: int,
    radius_full: int,
    panel_size: int,
    voxel_um: float,
) -> tuple[Image.Image, dict]:
    midpoint = np.asarray(row["exact_mid_xyz"], dtype=float)
    z_mid = int(round(midpoint[2] / scale))
    radius_level = int(math.ceil(radius_full / scale))
    sz, sy, sx = cache.pyr.shapes[cache.level]
    curve_z_lo = int(math.ceil(points[0, 2] / scale))
    curve_z_hi = int(math.floor(points[-1, 2] / scale)) + 1
    z_lo = max(0, curve_z_lo, z_mid - radius_level)
    z_hi = min(sz, curve_z_hi, z_mid + radius_level)
    require(z_hi - z_lo >= 2, "not enough in-curve z rows for orthogonal review")
    if axis == "y":
        other_mid = midpoint[0] / scale
        other_size = sx
        held_index, other_index = 1, 0
        plane_name = "Candidate-following XZ"
        held_name, other_name = "y(z)", "x(z)"
    else:
        other_mid = midpoint[1] / scale
        other_size = sy
        held_index, other_index = 0, 1
        plane_name = "Candidate-following YZ"
        held_name, other_name = "x(z)", "y(z)"
    z_values = np.arange(z_lo, z_hi, dtype=float)
    xy_level = curve_xy_level(points, z_values, scale)
    trajectory = xy_level[:, other_index]
    other_lo, other_hi, expanded = candidate_window(
        other_mid,
        trajectory,
        radius_level,
        other_size,
    )

    def fixed_of_z(z_level: int) -> float:
        index = z_level - z_lo
        return float(xy_level[index, held_index])

    raw = curved_plane_along_z(
        cache,
        axis,
        fixed_of_z,
        z_lo,
        z_hi,
        other_lo,
        other_hi,
    )
    require(raw.size > 0 and bool(np.any(raw)), "orthogonal source panel is empty")
    clean = resize_isotropic(Image.fromarray(enhance(raw)).convert("RGB"), panel_size)
    overlay = clean.copy()
    overlay_curve(
        overlay,
        xy_level[:, other_index],
        other_lo=other_lo,
        other_hi=other_hi,
        midpoint_other=other_mid,
        midpoint_z=midpoint[2] / scale,
        z_lo=z_lo,
        z_hi=z_hi,
    )
    extent_full = float(max(other_hi - other_lo - 1, 1) * scale)
    add_scale_bar(clean, extent_full, voxel_um)
    add_scale_bar(overlay, extent_full, voxel_um)
    segment_number = row["segment_index"] + 1
    clean = titled(
        clean,
        f"{plane_name} - marker-free",
        f"segment {segment_number}; plane follows {held_name}; vertical=z",
    )
    overlay = titled(
        overlay,
        f"{plane_name} - identical pixels + candidate",
        f"red={other_name} linear interpolation; circle=midpoint z={midpoint[2]:.0f}",
    )
    pair = Image.new("RGB", (clean.width + overlay.width + 10, clean.height), BACKGROUND)
    pair.paste(clean, (0, 0))
    pair.paste(overlay, (clean.width + 10, 0))
    metadata = {
        "axis": axis,
        "held_coordinate": held_name,
        "other_coordinate": other_name,
        "z_level_range": [z_lo, z_hi],
        "other_level_range": [other_lo, other_hi],
        "candidate_other_level_range": [float(trajectory.min()), float(trajectory.max())],
        "window_expanded_for_candidate": expanded,
        "isotropic_display": True,
        "display_size_pixels": list(clean.size),
        "full_resolution_extents_voxels": {
            "horizontal": max(other_hi - other_lo - 1, 1) * scale,
            "vertical_z": max(z_hi - z_lo - 1, 1) * scale,
        },
    }
    return pair, metadata


def render_segment(
    cache: ChunkCache,
    points: np.ndarray,
    row: dict,
    *,
    scale: int,
    radius_full: int,
    panel_size: int,
    voxel_um: float,
) -> tuple[Image.Image, list[dict]]:
    panels, metadata = [], []
    for axis in ("y", "x"):
        panel, record = render_plane_pair(
            cache,
            points,
            row,
            axis=axis,
            scale=scale,
            radius_full=radius_full,
            panel_size=panel_size,
            voxel_um=voxel_um,
        )
        panels.append(panel)
        metadata.append(record)
    gap, footer = 10, 42
    result = Image.new(
        "RGB",
        (max(p.width for p in panels), sum(p.height for p in panels) + gap + footer),
        BACKGROUND,
    )
    draw = ImageDraw.Draw(result)
    y = 0
    for panel in panels:
        result.paste(panel, (0, y))
        y += panel.height + gap
    midpoint = row["exact_mid_xyz"]
    draw.text(
        (12, result.height - 30),
        f"segment {row['segment_index'] + 1}; midpoint xyz=({midpoint[0]:.1f}, {midpoint[1]:.1f}, {midpoint[2]:.0f})",
        fill=TEXT,
        font=font(16, True),
    )
    return result, metadata


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scroll", required=True, choices=DEFAULT_SCROLLS)
    parser.add_argument("--segment", type=int, action="append", required=True)
    parser.add_argument("--curve", type=Path, help="Defaults to manual/<scroll>_umbilicus.json.")
    parser.add_argument("--level", type=int, choices=(2, 3, 4), default=3)
    parser.add_argument("--radius", type=int, default=1200)
    parser.add_argument("--panel-size", type=int, default=620)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--output-dir", type=Path, default=root / "audit" / "ct_review_local" / "orthogonals")
    parser.add_argument("--manifest-dir", type=Path, default=root / "audit" / "midpoint_density")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent
    curve = args.curve or root / "manual" / f"{args.scroll}_umbilicus.json"
    points = load_curve(curve)
    stream = scroll_volume_path(args.scroll, SCROLLS[args.scroll]["ct"])
    pyramid = open_pyramid(stream)
    scale = pyramid.scale(args.level)
    all_rows = segment_rows(points, scale)
    rows = select_segment_rows(all_rows, args.segment)
    slug = selection_slug(rows)
    output_dir = args.output_dir / args.scroll / f"level{args.level}_segments_{slug}"
    output_dir.mkdir(parents=True, exist_ok=True)
    cache = ChunkCache(pyramid, args.level, workers=args.workers, strict=True)
    outputs, segments = [], []
    for row in rows:
        image, planes = render_segment(
            cache,
            points,
            row,
            scale=scale,
            radius_full=args.radius,
            panel_size=args.panel_size,
            voxel_um=float(SCROLLS[args.scroll]["um"]),
        )
        name = f"{args.scroll}_segment_{row['segment_index'] + 1:03d}_orthogonals.png"
        image.save(output_dir / name, optimize=True)
        outputs.append(portable_path(output_dir / name, root))
        segments.append(
            {
                "segment_index": row["segment_index"],
                "segment_number": row["segment_index"] + 1,
                "exact_mid_xyz": row["exact_mid_xyz"],
                "planes": planes,
            }
        )
    args.manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.manifest_dir / f"{args.scroll}_orthogonal_level{args.level}_segments_{slug}.json"
    manifest = {
        "format": "umbilicus-midpoint-orthogonal-review-v1",
        "claim_boundary": "Candidate-following reviewer planes; no automatic correctness verdict.",
        "scroll": args.scroll,
        "curve": {"path": portable_path(curve, root), "sha256": sha256(curve)},
        "source_stream": f"https://vesuvius-challenge-open-data.s3.amazonaws.com/{stream}",
        "render": {
            "level": args.level,
            "scale": scale,
            "radius_full_voxels": args.radius,
            "panel_size": args.panel_size,
            "strict_chunk_fetch": True,
            "outputs_local": outputs,
        },
        "segments": segments,
        "bytes_fetched": cache.bytes_fetched,
        "missing_source_chunks": cache.missing_chunks,
        "failed_source_chunks": cache.failed_chunks,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        f"{args.scroll}: {len(rows)} orthogonal packs, {cache.bytes_fetched / 1e6:.1f} MB, "
        f"{cache.missing_chunks} Zarr fill chunks, {cache.failed_chunks} failed chunks"
    )
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
