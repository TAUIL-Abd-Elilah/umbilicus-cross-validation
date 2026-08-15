"""Build labelled z-slice montages for visual umbilicus picking, and map picks back.

Each montage panel is a fixed-size window of one z-slice, centred on the scroll
body centroid (or on a supplied anchor), rendered at a known number of full-res
voxels per pixel and overlaid with a labelled pixel grid.  A pick is then just a
panel index plus a pixel coordinate, which `picks_to_points` converts back into
full-resolution volume coordinates using the manifest written alongside the image.

Keeping the geometry in a manifest instead of in the reader's head is what makes
the picking step reproducible: the same manifest plus the same pixel picks always
yields the same control points.
"""

from __future__ import annotations

import json
import os

import numpy as np
from PIL import Image, ImageDraw

from coarse_center import body_centroid


def _enhance(a: np.ndarray, clip_limit: float = 2.5, tiles: int = 8) -> np.ndarray:
    """Local contrast enhancement (CLAHE), then a mild gamma lift.

    A global percentile stretch washes these scans out: the papyrus occupies a
    narrow intensity band that shifts across the cross-section, so one global
    window either crushes the outer windings or saturates the core.  Equalising
    in tiles keeps the lamellae visible everywhere at once, which is what the
    picking step actually needs.
    """
    v = a[a > 0]
    if v.size < 64:
        return a
    try:
        import cv2

        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tiles, tiles))
        out = clahe.apply(a).astype(np.float32) / 255.0
    except Exception:
        # skimage fallback keeps this runnable without OpenCV
        from skimage import exposure

        out = exposure.equalize_adapthist(a, clip_limit=clip_limit / 100.0).astype(np.float32)
    # gamma lift: equalisation leaves these scans dark in the mid-tones, and the
    # lamellae we are reading live exactly there
    out = np.clip(out, 0.0, 1.0) ** 0.72
    out = (out * 255.0).astype(np.uint8)
    # keep true background black so the body outline stays readable
    return np.where(a == 0, 0, out).astype(np.uint8)


def _autocontrast(a: np.ndarray, lo_pct: float = 1.0, hi_pct: float = 99.5) -> np.ndarray:
    return _enhance(a)


def build_montage(
    reader,
    scroll: str,
    zs: list[int],
    out_png: str,
    out_manifest: str,
    *,
    level: int = 3,
    window: int = 3072,
    panel_px: int = 360,
    cols: int = 4,
    anchors: dict[int, tuple[float, float]] | None = None,
    grid_step_px: int = 45,
    label_h: int = 22,
) -> dict:
    """Render `zs` as a grid of panels and write the geometry manifest.

    `anchors` maps z -> (y, x) full-res window centre; any z not present falls
    back to the automatic body centroid.
    """
    scale = reader.pyr.scale(level)
    win_px = int(round(window / scale))
    rows = int(np.ceil(len(zs) / cols))
    W = cols * panel_px
    H = rows * (panel_px + label_h)

    canvas = Image.new("RGB", (W, H), (12, 12, 12))
    draw = ImageDraw.Draw(canvas)
    panels = []

    for i, z in enumerate(zs):
        r, c = divmod(i, cols)
        ox, oy = c * panel_px, r * (panel_px + label_h) + label_h

        if anchors and z in anchors:
            cy, cx = anchors[z]
        else:
            got = body_centroid(reader, z)
            if got is None:
                draw.text((ox + 4, oy + 4), f"[{i}] z={z} EMPTY", fill=(255, 90, 90))
                panels.append({"index": i, "z": int(z), "empty": True})
                continue
            cy, cx = got

        y0 = int(round((cy - window / 2) / scale))
        x0 = int(round((cx - window / 2) / scale))
        zl = max(0, min(reader.pyr.shapes[level][0] - 1, int(round(z / scale))))
        img = reader.read_window(level, zl, y0, y0 + win_px, x0, x0 + win_px)
        img = _autocontrast(img)

        pil = Image.fromarray(img).resize((panel_px, panel_px), Image.BILINEAR)
        canvas.paste(pil, (ox, oy))

        # grid + ticks, drawn in a colour that never occurs in the greyscale data
        for g in range(grid_step_px, panel_px, grid_step_px):
            draw.line([(ox + g, oy), (ox + g, oy + panel_px)], fill=(0, 110, 0), width=1)
            draw.line([(ox, oy + g), (ox + panel_px, oy + g)], fill=(0, 110, 0), width=1)
            draw.text((ox + g + 2, oy + 1), str(g), fill=(0, 200, 0))
            draw.text((ox + 2, oy + g + 1), str(g), fill=(0, 200, 0))
        draw.rectangle([ox, oy, ox + panel_px - 1, oy + panel_px - 1], outline=(70, 70, 70))
        draw.text((ox + 4, oy - label_h + 5), f"[{i}]  z={z}", fill=(255, 235, 120))

        panels.append(
            {
                "index": i,
                "z": int(z),
                "empty": False,
                "origin_px": [ox, oy],
                "panel_px": panel_px,
                # full-res voxels per rendered panel pixel
                "voxels_per_px": window / panel_px,
                # full-res coords of the panel's top-left corner
                "y0_full": y0 * scale,
                "x0_full": x0 * scale,
                "anchor_full": [float(cy), float(cx)],
            }
        )

    canvas.save(out_png)
    manifest = {
        "scroll": scroll,
        "level": level,
        "window_full": window,
        "panel_px": panel_px,
        "cols": cols,
        "png": os.path.basename(out_png),
        "panels": panels,
    }
    with open(out_manifest, "w") as fp:
        json.dump(manifest, fp, indent=1)
    return manifest


def picks_to_points(manifest: dict, picks: dict[int, tuple[float, float]]) -> list[dict]:
    """Convert {panel_index: (px, py)} into control points in full-res voxels.

    `px`/`py` are pixel coordinates *within the panel*, matching the drawn grid.
    """
    by_index = {p["index"]: p for p in manifest["panels"]}
    pts = []
    for idx, (px, py) in sorted(picks.items()):
        p = by_index[idx]
        if p.get("empty"):
            raise ValueError(f"panel {idx} was empty; it cannot be picked")
        vpp = p["voxels_per_px"]
        y = p["y0_full"] + py * vpp
        x = p["x0_full"] + px * vpp
        pts.append({"x": int(round(x)), "y": int(round(y)), "z": int(p["z"]), "score": 100})
    return pts


def write_umbilicus(points: list[dict], path: str, note: str | None = None) -> None:
    """Emit the Villa `umbilicus.json` schema consumed by the Spiral fitter."""
    import datetime

    pts = sorted(points, key=lambda p: p["z"])
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "control_points": pts,
        "metadata": {
            "z_grid_spacing": 0,
            "min_score_threshold": 0.75,
            "high_score_threshold": 0.75,
            "total_points": len(pts),
            "timestamp": now,
        },
    }
    if note:
        doc["metadata"]["note"] = note
    with open(path, "w") as fp:
        json.dump(doc, fp, indent=1)


def plan_zs(z_lo: int, z_hi: int, n: int, margin: float = 0.02) -> list[int]:
    """`n` evenly spaced z across [z_lo, z_hi], pulled in slightly from the ends.

    The extreme slices of a scan are often mostly air, which makes both the
    centroid anchor and the visual judgement unnecessarily hard.
    """
    span = z_hi - z_lo
    a, b = z_lo + margin * span, z_hi - margin * span
    return [int(round(v)) for v in np.linspace(a, b, n)]
