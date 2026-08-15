"""Tracking filmstrip: closely spaced z, all anchored on a common curve.

Static per-slice picking failed because the umbilicus has no local landmark
(PROTOCOL.md Amendment 02).  The signal that *does* exist is continuity along z —
the reference curves move a median of only 48-170 voxels between control points.

A filmstrip makes that continuity usable without an interactive viewer.  Every
panel is centred on the same smooth anchor curve (the seed), so the umbilicus
appears at a slowly drifting offset from panel centre rather than jumping around,
and it can be followed across panels the way an annotator follows it across
scroll-wheel steps.  Panels are ordered left-to-right, top-to-bottom so reading
order is z order.

The centre crosshair is drawn on every panel: it is the anchor, not a guess at the
umbilicus, and its purpose is to give the eye a fixed reference against which the
drift is visible.
"""

from __future__ import annotations

import json
import os

import numpy as np
from PIL import Image, ImageDraw

from montage import _enhance


def seed_interpolator(seed_points: list[dict]):
    """z (full-res) -> (y, x) full-res, from a seed curve, ignoring flagged points."""
    good = [p for p in seed_points if p.get("score", 100) > 0]
    if len(good) < 2:
        good = seed_points
    z = np.array([p["z"] for p in good], float)
    o = np.argsort(z)
    z = z[o]
    y = np.array([p["y"] for p in good], float)[o]
    x = np.array([p["x"] for p in good], float)[o]
    return lambda zz: (float(np.interp(zz, z, y)), float(np.interp(zz, z, x)))


def build_filmstrip(
    reader,
    scroll: str,
    zs: list[int],
    anchor_of_z,
    out_png: str,
    out_manifest: str,
    *,
    level: int = 2,
    window: int = 2048,
    panel_px: int = 256,
    cols: int = 6,
    label_h: int = 18,
    grid_step_px: int = 32,
) -> dict:
    scale = reader.pyr.scale(level)
    win_px = int(round(window / scale))
    rows = int(np.ceil(len(zs) / cols))
    canvas = Image.new("RGB", (cols * panel_px, rows * (panel_px + label_h)), (10, 10, 10))
    draw = ImageDraw.Draw(canvas)
    panels = []

    for i, z in enumerate(zs):
        r, c = divmod(i, cols)
        ox, oy = c * panel_px, r * (panel_px + label_h) + label_h
        ay, ax = anchor_of_z(z)

        y0 = int(round((ay - window / 2) / scale))
        x0 = int(round((ax - window / 2) / scale))
        zl = max(0, min(reader.pyr.shapes[level][0] - 1, int(round(z / scale))))
        img = _enhance(reader.read_window(level, zl, y0, y0 + win_px, x0, x0 + win_px))
        canvas.paste(Image.fromarray(img).resize((panel_px, panel_px), Image.BILINEAR), (ox, oy))

        for g in range(grid_step_px, panel_px, grid_step_px):
            draw.line([(ox + g, oy), (ox + g, oy + panel_px)], fill=(0, 90, 0))
            draw.line([(ox, oy + g), (ox + panel_px, oy + g)], fill=(0, 90, 0))
        # anchor crosshair: a fixed reference, NOT an umbilicus estimate
        h = panel_px // 2
        draw.line([(ox + h - 7, oy + h), (ox + h + 7, oy + h)], fill=(255, 80, 80))
        draw.line([(ox + h, oy + h - 7), (ox + h, oy + h + 7)], fill=(255, 80, 80))
        draw.rectangle([ox, oy, ox + panel_px - 1, oy + panel_px - 1], outline=(60, 60, 60))
        draw.text((ox + 3, oy - label_h + 3), f"[{i}] z={z}", fill=(255, 235, 120))

        panels.append(
            {
                "index": i,
                "z": int(z),
                "empty": False,
                "origin_px": [ox, oy],
                "panel_px": panel_px,
                "voxels_per_px": window / panel_px,
                "y0_full": y0 * scale,
                "x0_full": x0 * scale,
                "anchor_full": [ay, ax],
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
        "kind": "filmstrip",
        "panels": panels,
    }
    json.dump(manifest, open(out_manifest, "w"), indent=1)
    return manifest
