#!/usr/bin/env python3
"""Render a same-frame exact-CT review pack for two umbilicus annotations.

The output is local QC evidence. It combines a marker-free crop, an identical
crop with both candidates, equal-scale candidate-centred crops, and a nearby-z
sequence. It never decides which curve is correct.
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

from compare_independent_curves import DEFAULT_SCROLLS, interpolate_xy, load_curve
from scrolls import SCROLLS
from slicefetch import SliceReader, open_pyramid, scroll_volume_path


OURS = "#ff453a"
PUBLIC = "#00d9ff"
BACKGROUND = "#111318"
TEXT = "#f7f7f8"


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.is_file():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def enhanced(array: np.ndarray) -> np.ndarray:
    return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(array)


def point_at(points: np.ndarray, z: int) -> np.ndarray:
    if not points[0, 2] <= z <= points[-1, 2]:
        raise ValueError(f"z={z} outside curve range {points[0, 2]}-{points[-1, 2]}")
    return np.asarray([*interpolate_xy(points, np.asarray([z], dtype=float))[0], z])


def read_panel(
    reader: SliceReader,
    pyramid,
    *,
    z: int,
    centre_xy: tuple[float, float],
    radius_full: int,
    size: int,
) -> tuple[Image.Image, dict[str, float | int]]:
    level = 2
    scale = pyramid.scale(level)
    exact_z = int(round(z / scale)) * scale
    radius = int(math.ceil(radius_full / scale))
    cx, cy = centre_xy[0] / scale, centre_xy[1] / scale
    x0, y0 = int(round(cx)) - radius, int(round(cy)) - radius
    array = reader.read_window(
        level,
        exact_z // scale,
        y0,
        y0 + 2 * radius,
        x0,
        x0 + 2 * radius,
    )
    if not np.any(array):
        raise ValueError("source exact-CT crop is empty after Zarr fill handling")
    image = Image.fromarray(enhanced(array)).convert("RGB").resize(
        (size, size), Image.Resampling.BICUBIC
    )
    return image, {
        "level": level,
        "scale": scale,
        "exact_z": exact_z,
        "x0_level": x0,
        "y0_level": y0,
        "radius_level": radius,
        "size": size,
    }


def label_bar(image: Image.Image, title: str, subtitle: str = "") -> Image.Image:
    bar = 76
    out = Image.new("RGB", (image.width, image.height + bar), BACKGROUND)
    out.paste(image, (0, bar))
    draw = ImageDraw.Draw(out)
    draw.text((14, 10), title, font=font(24, True), fill=TEXT)
    if subtitle:
        draw.text((14, 42), subtitle, font=font(17), fill="#c9cbd1")
    return out


def marker(draw: ImageDraw.ImageDraw, xy: tuple[float, float], colour: str, square: bool) -> None:
    x, y = xy
    r = 18
    box = (x - r, y - r, x + r, y + r)
    if square:
        draw.rectangle(box, outline=colour, width=6)
    else:
        draw.ellipse(box, outline=colour, width=6)
    draw.line((x - 42, y, x - r - 4, y), fill=colour, width=5)
    draw.line((x + r + 4, y, x + 42, y), fill=colour, width=5)
    draw.line((x, y - 42, x, y - r - 4), fill=colour, width=5)
    draw.line((x, y + r + 4, x, y + 42), fill=colour, width=5)


def panel_pixel(point: np.ndarray, frame: dict[str, float | int]) -> tuple[float, float]:
    scale = float(frame["scale"])
    radius = float(frame["radius_level"])
    size = float(frame["size"])
    x = (point[0] / scale - float(frame["x0_level"])) / (2 * radius) * size
    y = (point[1] / scale - float(frame["y0_level"])) / (2 * radius) * size
    return x, y


def add_scale_bar(
    image: Image.Image,
    radius_full: int,
    voxel_size_um: float,
    length_mm: float = 5.0,
) -> None:
    pixels = length_mm * 1000.0 / voxel_size_um / (2 * radius_full) * image.width
    x1, y = image.width - 34, image.height - 34
    x0 = x1 - pixels
    draw = ImageDraw.Draw(image)
    draw.rectangle((x0 - 4, y - 18, x1 + 4, y + 14), fill="#111318")
    draw.line((x0, y, x1, y), fill="white", width=5)
    draw.line((x0, y - 7, x0, y + 7), fill="white", width=4)
    draw.line((x1, y - 7, x1, y + 7), fill="white", width=4)
    draw.text((x0, y - 17), f"{length_mm:g} mm", font=font(15, True), fill="white")


def compose_grid(rows: list[list[Image.Image]], gap: int = 12) -> Image.Image:
    width = max(sum(image.width for image in row) + gap * (len(row) - 1) for row in rows)
    heights = [max(image.height for image in row) for row in rows]
    out = Image.new("RGB", (width, sum(heights) + gap * (len(rows) - 1)), BACKGROUND)
    y = 0
    for row, height in zip(rows, heights):
        x = (width - (sum(image.width for image in row) + gap * (len(row) - 1))) // 2
        for image in row:
            out.paste(image, (x, y))
            x += image.width + gap
        y += height + gap
    return out


def render(args: argparse.Namespace) -> tuple[Path, Path]:
    ours_path = args.ours_path or args.ours_dir / f"{args.scroll}_umbilicus.json"
    public_path = args.reference_dir / f"{args.scroll}_umbilicus.json"
    ours, public = load_curve(ours_path), load_curve(public_path)
    stream = scroll_volume_path(args.scroll, SCROLLS[args.scroll]["ct"])
    pyramid = open_pyramid(stream)
    output_dir = args.output_dir / args.scroll
    output_dir.mkdir(parents=True, exist_ok=True)
    reader = SliceReader(pyramid, cache_dir=str(args.cache_dir), workers=args.workers)
    scale = pyramid.scale(2)
    exact_z = int(round(args.z / scale)) * scale
    po, pp = point_at(ours, exact_z), point_at(public, exact_z)
    separation = float(np.linalg.norm(po[:2] - pp[:2]))
    centre = tuple(np.mean(np.asarray([po[:2], pp[:2]]), axis=0).tolist())
    radius = int(max(args.minimum_radius, math.ceil(separation / 2 + args.margin)))
    voxel_um = float(SCROLLS[args.scroll]["um"])

    clean, frame = read_panel(
        reader,
        pyramid,
        z=exact_z,
        centre_xy=centre,
        radius_full=radius,
        size=900,
    )
    overlay = clean.copy()
    overlay_draw = ImageDraw.Draw(overlay)
    ours_px, public_px = panel_pixel(po, frame), panel_pixel(pp, frame)
    overlay_draw.line((*ours_px, *public_px), fill="#ffffff", width=3)
    marker(overlay_draw, ours_px, OURS, False)
    marker(overlay_draw, public_px, PUBLIC, True)
    add_scale_bar(clean, radius, voxel_um)
    add_scale_bar(overlay, radius, voxel_um)

    clean = label_bar(clean, "Same CT frame — no markers", f"exact z={exact_z}; identical contrast and crop")
    overlay = label_bar(
        overlay,
        "Same CT frame — candidates overlaid",
        f"red circle=independent {tuple(int(value) for value in np.rint(po[:2]))}; "
        f"cyan square=public {tuple(int(value) for value in np.rint(pp[:2]))}; d={separation * voxel_um / 1000:.2f} mm",
    )

    centred = []
    for name, point, colour in (("Independent candidate", po, OURS), ("Public candidate", pp, PUBLIC)):
        panel, _ = read_panel(
            reader,
            pyramid,
            z=exact_z,
            centre_xy=(float(point[0]), float(point[1])),
            radius_full=args.candidate_radius,
            size=900,
        )
        add_scale_bar(panel, args.candidate_radius, voxel_um)
        centred.append(
            label_bar(
                panel,
                f"{name} — marker-free, equal scale",
                f"candidate is exactly at image centre; x={point[0]:.0f}, y={point[1]:.0f}, z={exact_z}; colour key {colour}",
            )
        )

    nearby = []
    for delta in (-400, -200, 0, 200, 400):
        panel, local_frame = read_panel(
            reader,
            pyramid,
            z=exact_z + delta,
            centre_xy=centre,
            radius_full=radius,
            size=350,
        )
        add_scale_bar(panel, radius, voxel_um)
        nearby.append(label_bar(panel, f"z={int(local_frame['exact_z'])}", "same centre, scale, no markers"))

    body = compose_grid([[clean, overlay], centred, nearby])
    header = 118
    pack = Image.new("RGB", (body.width, body.height + header), BACKGROUND)
    pack.paste(body, (0, header))
    draw = ImageDraw.Draw(pack)
    draw.text((18, 12), f"{args.scroll} exact-CT annotation review — z={exact_z}", font=font(34, True), fill=TEXT)
    draw.text(
        (18, 58),
        "Review the marker-free anatomy first, then compare the overlay and nearby slices. This figure records disagreement; it gives no automatic verdict.",
        font=font(20),
        fill="#c9cbd1",
    )

    output = output_dir / f"{args.scroll}_z{exact_z}_exact_ct_review.png"
    metadata = output.with_suffix(".json")
    pack.save(output, optimize=True)
    record = {
        "format": "exact-ct-umbilicus-review-pack-v1",
        "claim_boundary": "Two candidate annotations overlaid for human review; no automatic correctness verdict.",
        "scroll": args.scroll,
        "requested_z": args.z,
        "exact_z": exact_z,
        "source_stream": f"https://vesuvius-challenge-open-data.s3.amazonaws.com/{stream}",
        "ours": {"path": str(ours_path), "sha256": sha256(ours_path), "xyz": po.tolist()},
        "public": {"path": str(public_path), "sha256": sha256(public_path), "xyz": pp.tolist()},
        "distance_voxels": separation,
        "distance_mm": separation * voxel_um / 1000.0,
        "render": {
            "same_frame_centre_xy": list(centre),
            "same_frame_radius_voxels": radius,
            "candidate_radius_voxels": args.candidate_radius,
            "nearby_delta_z": [-400, -200, 0, 200, 400],
            "level": 2,
            "clahe_clip_limit": 2.0,
        },
        "bytes_fetched": reader.bytes_fetched,
        "missing_source_chunks": reader.missing_chunks,
        "failed_source_chunks": 0,
    }
    metadata.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return output, metadata


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--ours-dir", type=Path, default=root / "manual")
    parser.add_argument("--ours-path", type=Path, help="Optional single candidate curve override.")
    parser.add_argument("--scroll", required=True, choices=DEFAULT_SCROLLS)
    parser.add_argument("--z", required=True, type=int)
    parser.add_argument("--output-dir", type=Path, default=root / "audit" / "ct_review_local")
    parser.add_argument("--cache-dir", type=Path, default=root / "cache")
    parser.add_argument("--minimum-radius", type=int, default=1400)
    parser.add_argument("--margin", type=int, default=850)
    parser.add_argument("--candidate-radius", type=int, default=900)
    parser.add_argument("--workers", type=int, default=16)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output, metadata = render(args)
    print(output)
    print(metadata)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
