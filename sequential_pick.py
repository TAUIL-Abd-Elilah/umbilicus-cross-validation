"""Sequential umbilicus picking: each batch is anchored on the picks before it.

This is the one instrument the project had not tried.  Static montages failed
(PROTOCOL.md Amendment 01, median 432) because every panel was anchored on the
seed and judged independently, so an error at one z told you nothing at the next.
The reference curves were drawn in khartes, where an annotator carries the centre
forward through z and each placement is informed by the last.

Here the same property is obtained without a GUI: batch `k` is anchored on the
running track from batches `0..k-1`, carried forward along the seed's local drift

    anchor(z) = last_pick + (seed(z) - seed(z_last))

so the panel centre is a genuine prediction from prior decisions.  Four z per
image at 8 full-res voxels per pixel keeps both the winding context and the
resolution needed to place a point.

Usage:
    python sequential_pick.py PHerc0826 --batch 0
    # record picks into picks/PHerc0826_seq.json, then:
    python sequential_pick.py PHerc0826 --batch 1
"""

from __future__ import annotations

import argparse
import json
import os

import numpy as np
from PIL import Image, ImageDraw

from montage import _enhance, plan_zs
from scrolls import SCROLLS
from slicefetch import SliceReader, open_pyramid, scroll_volume_path

BATCH = 4


def seed_fn(points):
    good = [p for p in points if p.get("score", 100) > 0] or points
    z = np.array([p["z"] for p in good], float)
    o = np.argsort(z)
    z = z[o]
    y = np.array([p["y"] for p in good], float)[o]
    x = np.array([p["x"] for p in good], float)[o]
    return lambda zz: (float(np.interp(zz, z, y)), float(np.interp(zz, z, x)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scroll")
    ap.add_argument("--batch", type=int, required=True)
    ap.add_argument("--n-total", type=int, default=24)
    ap.add_argument("--window", type=int, default=4096)
    ap.add_argument("--level", type=int, default=3)
    ap.add_argument("--panel-px", type=int, default=512)
    args = ap.parse_args()

    meta = SCROLLS[args.scroll]
    pyr = open_pyramid(scroll_volume_path(args.scroll, meta["ct"]))
    reader = SliceReader(pyr, cache_dir="cache")
    scale = pyr.scale(args.level)

    seed_pts = json.load(open(f"seeds/{args.scroll}_umbilicus_seed.json"))["control_points"]
    seed = seed_fn(seed_pts)

    # Schedule over the range where the scroll body actually exists, not the raw
    # scan extent: `z_span` is a coarse occupancy probe and can start in air, which
    # wastes panels on empty slices.  The unflagged seed points are the strictest
    # body-presence evidence available without touching a reference curve.
    good = [p for p in seed_pts if p.get("score", 100) > 0]
    lo, hi = min(p["z"] for p in good), max(p["z"] for p in good)
    zs_all = plan_zs(lo, hi, args.n_total, margin=0.0)
    zs = zs_all[args.batch * BATCH : (args.batch + 1) * BATCH]
    if not zs:
        raise SystemExit(f"batch {args.batch} is past the end ({len(zs_all)} z total)")

    # running track from previously recorded batches
    track_path = f"picks/{args.scroll}_seq.json"
    track = []
    if os.path.exists(track_path):
        track = sorted(json.load(open(track_path))["points"], key=lambda p: p["z"])

    def anchor_for(z):
        if not track:
            return seed(z)
        last = track[-1]
        sy_last, sx_last = seed(last["z"])
        sy, sx = seed(z)
        # carry the last decision forward along the seed's local drift
        return last["y"] + (sy - sy_last), last["x"] + (sx - sx_last)

    canvas = Image.new("RGB", (2 * args.panel_px, 2 * (args.panel_px + 22)), (10, 10, 10))
    draw = ImageDraw.Draw(canvas)
    panels = []
    win_px = args.window // scale

    for i, z in enumerate(zs):
        r, c = divmod(i, 2)
        ox, oy = c * args.panel_px, r * (args.panel_px + 22) + 22
        ay, ax = anchor_for(z)
        y0 = int(round((ay - args.window / 2) / scale))
        x0 = int(round((ax - args.window / 2) / scale))
        zl = max(0, min(pyr.shapes[args.level][0] - 1, int(round(z / scale))))
        img = _enhance(reader.read_window(args.level, zl, y0, y0 + win_px, x0, x0 + win_px))
        canvas.paste(
            Image.fromarray(img).resize((args.panel_px, args.panel_px), Image.BILINEAR), (ox, oy)
        )

        step = 64
        for g in range(step, args.panel_px, step):
            draw.line([(ox + g, oy), (ox + g, oy + args.panel_px)], fill=(0, 95, 0))
            draw.line([(ox, oy + g), (ox + args.panel_px, oy + g)], fill=(0, 95, 0))
            draw.text((ox + g + 2, oy + 2), str(g), fill=(0, 210, 0))
            draw.text((ox + 2, oy + g + 2), str(g), fill=(0, 210, 0))
        h = args.panel_px // 2
        draw.line([(ox + h - 9, oy + h), (ox + h + 9, oy + h)], fill=(255, 70, 70), width=2)
        draw.line([(ox + h, oy + h - 9), (ox + h, oy + h + 9)], fill=(255, 70, 70), width=2)
        draw.rectangle(
            [ox, oy, ox + args.panel_px - 1, oy + args.panel_px - 1], outline=(70, 70, 70)
        )
        draw.text((ox + 4, oy - 18), f"[{i}] z={z}   anchor=({ay:.0f},{ax:.0f})", fill=(255, 235, 120))

        panels.append(
            {
                "index": i,
                "z": int(z),
                "origin_px": [ox, oy],
                "panel_px": args.panel_px,
                "voxels_per_px": args.window / args.panel_px,
                "y0_full": y0 * scale,
                "x0_full": x0 * scale,
                "anchor_full": [ay, ax],
            }
        )

    out_png = f"picking/{args.scroll}_seq{args.batch}.png"
    out_man = f"picking/{args.scroll}_seq{args.batch}.json"
    os.makedirs("picking", exist_ok=True)
    canvas.save(out_png)
    json.dump(
        {
            "scroll": args.scroll,
            "batch": args.batch,
            "level": args.level,
            "window_full": args.window,
            "png": os.path.basename(out_png),
            "panels": panels,
        },
        open(out_man, "w"),
        indent=1,
    )
    print(f"batch {args.batch}: z {zs} -> {out_png}")
    print(f"  {args.window / args.panel_px:.1f} voxels/px, "
          f"track has {len(track)} prior points, {reader.bytes_fetched/1e6:.1f} MB")


if __name__ == "__main__":
    main()
