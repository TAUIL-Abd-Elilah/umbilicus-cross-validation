#!/usr/bin/env python3
"""Render exact-CT midpoint checks for an umbilicus control polyline.

Every adjacent-control segment is checked at its z midpoint.  The left panel is
marker-free and the right panel is the identical CT crop with the linearly
interpolated point marked.  Risk scores only prioritize review; they are not an
accuracy metric and every segment must still receive a human classification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from compare_independent_curves import DEFAULT_SCROLLS, load_curve
from scrolls import SCROLLS
from slicefetch import SliceReader, open_pyramid, scroll_volume_path


BACKGROUND = "#111318"
TEXT = "#f7f7f8"
MUTED = "#c9cbd1"
MARKER = "#ff453a"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ),
    ]
    for path in candidates:
        if path.is_file():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def portable_path(path: Path, root: Path) -> str:
    """Return a public receipt path without exposing a runner's local directory."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return f"external-input/{path.name}"


def enhance(array: np.ndarray) -> np.ndarray:
    return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(array)


def turn_angle_degrees(left: np.ndarray, right: np.ndarray) -> float:
    left_norm = float(np.linalg.norm(left))
    right_norm = float(np.linalg.norm(right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    cosine = float(np.dot(left, right) / (left_norm * right_norm))
    return float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))


def segment_rows(points: np.ndarray, level_scale: int) -> list[dict]:
    vectors = np.diff(points, axis=0)
    dxy = np.linalg.norm(vectors[:, :2], axis=1)
    dz = vectors[:, 2]
    require(bool(np.all(dz > 0)), "control z must increase")
    speeds = dxy / dz
    # Rank bends in the image plane. Including z makes large slice gaps
    # dominate the vectors and hides the sharp XY turns we need to review.
    turns = [
        turn_angle_degrees(vectors[i - 1, :2], vectors[i, :2])
        for i in range(1, len(vectors))
    ]
    median_dxy = max(float(np.median(dxy)), 1.0)
    median_dz = max(float(np.median(dz)), 1.0)

    rows = []
    for index, (start, end) in enumerate(zip(points[:-1], points[1:])):
        requested_mid = (float(start[2]) + float(end[2])) / 2.0
        first_level_z = int(math.ceil(float(start[2]) / level_scale))
        last_level_z = int(math.floor(float(end[2]) / level_scale))
        require(
            first_level_z <= last_level_z,
            f"segment {index + 1} has no pyramid-aligned slice at scale {level_scale}",
        )
        exact_level_z = max(
            first_level_z,
            min(last_level_z, int(round(requested_mid / level_scale))),
        )
        exact_z = exact_level_z * level_scale
        fraction = (exact_z - start[2]) / (end[2] - start[2])
        midpoint = start + fraction * (end - start)
        left_turn = turns[index - 1] if index > 0 else 0.0
        right_turn = turns[index] if index < len(turns) else 0.0
        max_turn = max(left_turn, right_turn)
        risk = float(dxy[index] / median_dxy + dz[index] / median_dz + max_turn / 45.0)
        rows.append(
            {
                "segment_index": index,
                "start_xyz": [float(value) for value in start],
                "end_xyz": [float(value) for value in end],
                "requested_mid_z": requested_mid,
                "exact_mid_xyz": [float(value) for value in midpoint],
                "delta_z": float(dz[index]),
                "delta_xy_voxels": float(dxy[index]),
                "xy_speed_per_z": float(speeds[index]),
                "left_turn_degrees": float(left_turn),
                "right_turn_degrees": float(right_turn),
                "risk_score": risk,
                "classification": "UNREVIEWED",
                "review_note": "",
            }
        )
    order = sorted(range(len(rows)), key=lambda i: (-rows[i]["risk_score"], i))
    for rank, index in enumerate(order, 1):
        rows[index]["risk_rank"] = rank
    return rows


def select_segment_rows(rows: list[dict], requested: list[int] | None) -> list[dict]:
    """Select one-based segment numbers while preserving curve order."""
    if not requested:
        return rows
    unique = sorted(set(requested))
    invalid = [number for number in unique if number < 1 or number > len(rows)]
    require(not invalid, f"segment numbers outside 1..{len(rows)}: {invalid}")
    return [rows[number - 1] for number in unique]


def selection_slug(rows: list[dict]) -> str:
    return "-".join(f"{row['segment_index'] + 1:03d}" for row in rows)


def read_crop(
    reader: SliceReader,
    pyramid,
    point: np.ndarray,
    radius_full: int,
    size: int,
    level: int,
) -> tuple[Image.Image, dict]:
    scale = pyramid.scale(level)
    z = int(point[2])
    radius = int(math.ceil(radius_full / scale))
    cx, cy = point[0] / scale, point[1] / scale
    x0, y0 = int(round(cx)) - radius, int(round(cy)) - radius
    crop = reader.read_window(level, z // scale, y0, y0 + 2 * radius, x0, x0 + 2 * radius)
    require(bool(np.any(crop)), "source midpoint crop is empty after Zarr fill handling")
    image = Image.fromarray(enhance(crop)).convert("RGB").resize(
        (size, size), Image.Resampling.BICUBIC
    )
    return image, {
        "level": level,
        "scale": scale,
        "x0_level": x0,
        "y0_level": y0,
        "radius_level": radius,
        "size": size,
    }


def point_pixel(point: np.ndarray, frame: dict) -> tuple[float, float]:
    scale = frame["scale"]
    diameter = 2 * frame["radius_level"]
    return (
        (point[0] / scale - frame["x0_level"]) / diameter * frame["size"],
        (point[1] / scale - frame["y0_level"]) / diameter * frame["size"],
    )


def marker(draw: ImageDraw.ImageDraw, xy: tuple[float, float]) -> None:
    x, y = xy
    radius = 16
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=MARKER, width=5)
    for line in (
        (x - 38, y, x - radius - 4, y),
        (x + radius + 4, y, x + 38, y),
        (x, y - 38, x, y - radius - 4),
        (x, y + radius + 4, x, y + 38),
    ):
        draw.line(line, fill=MARKER, width=4)


def scale_bar(image: Image.Image, radius_full: int, voxel_um: float) -> None:
    length_mm = 5.0
    pixels = length_mm * 1000.0 / voxel_um / (2 * radius_full) * image.width
    x1, y = image.width - 24, image.height - 24
    x0 = x1 - pixels
    draw = ImageDraw.Draw(image)
    draw.rectangle((x0 - 5, y - 19, x1 + 5, y + 12), fill=BACKGROUND)
    draw.line((x0, y, x1, y), fill="white", width=4)
    draw.line((x0, y - 6, x0, y + 6), fill="white", width=3)
    draw.line((x1, y - 6, x1, y + 6), fill="white", width=3)
    draw.text((x0, y - 18), "5 mm", fill="white", font=font(14, True))


def titled(image: Image.Image, title: str, subtitle: str) -> Image.Image:
    bar = 70
    out = Image.new("RGB", (image.width, image.height + bar), BACKGROUND)
    out.paste(image, (0, bar))
    draw = ImageDraw.Draw(out)
    draw.text((10, 8), title, fill=TEXT, font=font(20, True))
    draw.text((10, 37), subtitle, fill=MUTED, font=font(15))
    return out


def pair_panel(
    reader: SliceReader,
    pyramid,
    row: dict,
    radius_full: int,
    panel_size: int,
    voxel_um: float,
    level: int,
) -> Image.Image:
    point = np.asarray(row["exact_mid_xyz"], dtype=float)
    clean, frame = read_crop(reader, pyramid, point, radius_full, panel_size, level)
    overlay = clean.copy()
    marker(ImageDraw.Draw(overlay), point_pixel(point, frame))
    scale_bar(clean, radius_full, voxel_um)
    scale_bar(overlay, radius_full, voxel_um)
    start, end = row["start_xyz"], row["end_xyz"]
    base = (
        f"segment {row['segment_index'] + 1}; controls z={start[2]:.0f}→{end[2]:.0f}; "
        f"mid z={point[2]:.0f}; Δxy={row['delta_xy_voxels']:.0f}; risk rank {row['risk_rank']}"
    )
    left = titled(clean, "Marker-free exact CT", base)
    right = titled(
        overlay,
        "Identical crop with linear midpoint",
        f"red=interpolated ({point[0]:.0f}, {point[1]:.0f}); inspect branch placement",
    )
    gap = 10
    result = Image.new("RGB", (left.width + right.width + gap, max(left.height, right.height)), BACKGROUND)
    result.paste(left, (0, 0))
    result.paste(right, (left.width + gap, 0))
    return result


def make_pages(panels: list[Image.Image], output_dir: Path, scroll: str, rows_per_page: int) -> list[str]:
    names = []
    for page_index in range(math.ceil(len(panels) / rows_per_page)):
        subset = panels[page_index * rows_per_page : (page_index + 1) * rows_per_page]
        gap, header = 10, 88
        width = max(panel.width for panel in subset)
        height = header + sum(panel.height for panel in subset) + gap * (len(subset) - 1)
        page = Image.new("RGB", (width, height), BACKGROUND)
        draw = ImageDraw.Draw(page)
        draw.text(
            (14, 10),
            f"{scroll} — exact-CT midpoint density audit — page {page_index + 1}",
            fill=TEXT,
            font=font(28, True),
        )
        draw.text(
            (14, 49),
            "Review every row: PASS, ADD_CONTROL, or AMBIGUOUS. Clean and marked panels use identical pixels.",
            fill=MUTED,
            font=font(17),
        )
        y = header
        for panel in subset:
            page.paste(panel, (0, y))
            y += panel.height + gap
        name = f"{scroll}_midpoints_page_{page_index + 1:02d}.png"
        page.save(output_dir / name, optimize=True)
        names.append(name)
    return names


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scroll", required=True, choices=DEFAULT_SCROLLS)
    parser.add_argument("--curve", type=Path, help="Defaults to manual/<scroll>_umbilicus.json.")
    parser.add_argument("--output-dir", type=Path, default=root / "audit" / "ct_review_local" / "midpoints")
    parser.add_argument("--manifest-dir", type=Path, default=root / "audit" / "midpoint_density")
    parser.add_argument("--cache-dir", type=Path, default=root / "audit" / "ct_review_cache" / "midpoints")
    parser.add_argument("--radius", type=int, default=1600)
    parser.add_argument("--panel-size", type=int, default=620)
    parser.add_argument("--rows-per-page", type=int, default=4)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument(
        "--level",
        type=int,
        choices=(2, 3),
        default=3,
        help="Pyramid level: 3 for fast screening, 2 for escalated review.",
    )
    parser.add_argument(
        "--segment",
        type=int,
        action="append",
        help="Render only this one-based interval; repeat for multiple intervals.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent
    curve = args.curve or root / "manual" / f"{args.scroll}_umbilicus.json"
    points = load_curve(curve)
    stream = scroll_volume_path(args.scroll, SCROLLS[args.scroll]["ct"])
    pyramid = open_pyramid(stream)
    level_scale = pyramid.scale(args.level)
    all_rows = segment_rows(points, level_scale)
    rows = select_segment_rows(all_rows, args.segment)
    out = args.output_dir / args.scroll
    if args.segment:
        out = out / f"level{args.level}_segments_{selection_slug(rows)}"
    out.mkdir(parents=True, exist_ok=True)
    reader = SliceReader(
        pyramid,
        cache_dir=str(args.cache_dir / args.scroll),
        workers=args.workers,
    )
    panels = [
        pair_panel(
            reader,
            pyramid,
            row,
            args.radius,
            args.panel_size,
            float(SCROLLS[args.scroll]["um"]),
            args.level,
        )
        for row in rows
    ]
    pages = make_pages(panels, out, args.scroll, args.rows_per_page)
    args.manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_name = f"{args.scroll}_midpoint_audit.json"
    if args.segment:
        manifest_name = f"{args.scroll}_level{args.level}_segments_{selection_slug(rows)}.json"
    manifest_path = args.manifest_dir / manifest_name
    manifest = {
        "format": "umbilicus-midpoint-density-audit-v1",
        "claim_boundary": (
            "Risk ranks prioritize human review only. A midpoint is acceptable only after exact-CT "
            "classification; this manifest contains no automatic correctness verdict."
        ),
        "scroll": args.scroll,
        "curve": {
            "path": portable_path(curve, root),
            "sha256": sha256(curve),
            "control_count": len(points),
        },
        "source_stream": f"https://vesuvius-challenge-open-data.s3.amazonaws.com/{stream}",
        "render": {
            "level": args.level,
            "scale": level_scale,
            "radius_full_voxels": args.radius,
            "panel_size": args.panel_size,
            "clahe_clip_limit": 2.0,
            "pages_local": [portable_path(out / page, root) for page in pages],
        },
        "review_contract": {
            "allowed_classifications": ["PASS", "ADD_CONTROL", "AMBIGUOUS"],
            "add_control_rule": "Place a new independent Khartes control at the reviewed CT core; never copy another curve.",
            "completion": "Every segment must be classified; all ADD_CONTROL segments must be re-rendered after editing.",
        },
        "selected_segment_numbers": [row["segment_index"] + 1 for row in rows],
        "segments": rows,
        "bytes_fetched": reader.bytes_fetched,
        "missing_source_chunks": reader.missing_chunks,
        "failed_source_chunks": 0,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        f"{args.scroll}: {len(rows)} midpoints, {len(pages)} pages, "
        f"{reader.bytes_fetched / 1e6:.1f} MB, {reader.missing_chunks} Zarr fill chunks"
    )
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
