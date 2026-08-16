#!/usr/bin/env python3
"""Plot six independent umbilicus pairs without redistributing CT imagery."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from compare_independent_curves import DEFAULT_SCROLLS, interpolate_xy, load_curve
from scrolls import SCROLLS


OURS = "#f97316"
REFERENCE = "#06b6d4"


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ours-dir", type=Path, default=root / "manual")
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=root / "audit" / "comparison_overview.png")
    parser.add_argument("--threshold-mm", type=float, default=1.81)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plt.style.use("dark_background")
    figure, axes = plt.subplots(len(DEFAULT_SCROLLS), 2, figsize=(14, 22), constrained_layout=True)

    for row, scroll in enumerate(DEFAULT_SCROLLS):
        ours = load_curve(args.ours_dir / f"{scroll}_umbilicus.json")
        reference = load_curve(args.reference_dir / f"{scroll}_umbilicus.json")
        lo = int(np.ceil(max(ours[0, 2], reference[0, 2])))
        hi = int(np.floor(min(ours[-1, 2], reference[-1, 2])))
        z = np.arange(lo, hi + 1, dtype=np.float64)
        ours_xy = interpolate_xy(ours, z)
        reference_xy = interpolate_xy(reference, z)
        distance_mm = np.linalg.norm(ours_xy - reference_xy, axis=1) * SCROLLS[scroll]["um"] / 1000.0

        trajectory, distance = axes[row]
        trajectory.plot(ours[:, 0], ours[:, 1], "o-", color=OURS, lw=1.4, ms=2.8, label="independent")
        trajectory.plot(reference[:, 0], reference[:, 1], "o-", color=REFERENCE, lw=1.4, ms=2.8, label="public")
        trajectory.set_title(f"{scroll} — XY control trajectory")
        trajectory.set_xlabel("x (level-0 voxels)")
        trajectory.set_ylabel("y (level-0 voxels)")
        trajectory.invert_yaxis()
        trajectory.set_aspect("equal", adjustable="datalim")
        trajectory.grid(alpha=0.15)
        if row == 0:
            trajectory.legend(frameon=False)

        distance.plot(z, distance_mm, color="#a78bfa", lw=1.5)
        distance.axhline(
            args.threshold_mm,
            color="#facc15",
            ls="--",
            lw=1.0,
            label="1.81 mm reporting line",
        )
        peak = int(np.argmax(distance_mm))
        distance.scatter([z[peak]], [distance_mm[peak]], color="#fb7185", s=22, zorder=3)
        distance.annotate(
            f"{distance_mm[peak]:.2f} mm\nz={int(z[peak])}",
            (z[peak], distance_mm[peak]),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=8,
        )
        distance.set_title("Same-z lateral disagreement")
        distance.set_xlabel("z (level-0 voxels)")
        distance.set_ylabel("distance (mm)")
        distance.set_ylim(bottom=0)
        distance.grid(alpha=0.15)
        if row == 0:
            distance.legend(frameon=False)

    figure.suptitle(
        "Six independent umbilicus annotations vs public curves\n"
        "Disagreement identifies CT-review regions; it does not identify ground truth",
        fontsize=16,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.output, dpi=170, facecolor=figure.get_facecolor())
    plt.close(figure)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
