#!/usr/bin/env python
"""Build a ready-to-draw Khartes project for one scroll's manual umbilicus pass.

The manual pass is the whole deliverable, so every minute that is not drawing is
waste.  Steps 1-3 of `handoff/KHARTES_TODO.md` (new project, attach the OME/Zarr
stream, import both automatic guides, deactivate them, create a blank output
fragment) are pure setup and are all plain JSON on disk.  This writes that
project directly, so the operator opens it and starts drawing.

    python make_operator_project.py PHerc0191

produces `_operator_projects/PHerc0191-manual.khprj` containing

    project.json                     name, voxel size, timestamps
    volumes/<scroll>.volzarr         the exact public stream from scrolls.py
    fragments/all.json               both guides + a blank output fragment
    views.json                       guides off, blank output active, view
                                     parked on the first guide control

Step 6 (fresh-project reimport of the exported candidate) is the same trick:

    python make_operator_project.py PHerc0191 --candidate \\
        manual/candidates/PHerc0191_umbilicus.candidate.json

produces `PHerc0191-roundtrip.khprj` holding only that candidate, attached to
the same stream, for the independent human check.

Nothing here approves anything.  It writes editor scaffolding only; the
candidate-first promotion path in `approve_manual_curve.py` and
`verify_manual_release.py` is unchanged.  Projects are never overwritten
without `--force`.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys
import time
from datetime import datetime, timezone

from scrolls import SCROLLS

BUCKET = "https://vesuvius-challenge-open-data.s3.amazonaws.com"

DEFAULT_OUT = pathlib.Path(__file__).resolve().parent.parent / "_operator_projects"

# Guides stay dim; the fragment being drawn is the bright one.
COLOR_SEED = "#8a8a8a"
COLOR_ESTIMATE = "#0fafff"
COLOR_MANUAL = "#ffd21f"
COLOR_CANDIDATE = "#42ff25"

# Khartes writes zoom as whatever the operator left; this is the scale the
# PHerc1203 pass actually worked at.
DEFAULT_ZOOM = 0.25


def stream_url(scroll: str) -> str:
    """Exact public OME/Zarr stream for `scroll`, as recorded in scrolls.py."""
    return f"{BUCKET}/{scroll}/volumes/{SCROLLS[scroll]['ct']}"


def timestamp(offset_s: float = 0.0) -> str:
    """A Khartes-style timestamp: 2026-08-15T10:57:13.64Z."""
    now = datetime.now(timezone.utc).timestamp() + offset_s
    dt = datetime.fromtimestamp(now, timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 10000:02d}Z"


def load_controls(path: pathlib.Path) -> list[list[float]]:
    """Read Villa `control_points` as Khartes gpoints, ordered by z.

    Khartes stores a point as [x, y, z]; the JSON schema stores named fields.
    """
    info = json.loads(path.read_text(encoding="utf8"))
    points = info["control_points"]
    if not points:
        raise ValueError(f"{path} has no control_points")
    rows = [[float(p["x"]), float(p["y"]), float(p["z"])] for p in points]
    rows.sort(key=lambda r: r[2])
    return rows


def fragment(name: str, points: list[list[float]], color: str, created: str) -> dict:
    """One umbilicus fragment in the on-disk shape Khartes' loader expects.

    `manual_points` is the canonical control set on the repaired branch;
    `gpoints` is its display copy.  Both are written so a project built here
    round-trips through save/reopen exactly like one built in the GUI.
    """
    return {
        "name": name,
        "created": created,
        "modified": created,
        "direction": 1,
        "color": color,
        "params": {},
        "type": "U",
        "gpoints": points,
        "manual_points": points,
    }


def view_position(points: list[list[float]]) -> list[float]:
    """Khartes' transposed cursor for the lowest-z control.

    With `direction: 1` the saved triple is [x, z, y] — confirmed against every
    PHerc1203 project written by Khartes itself.
    """
    x, y, z = points[0]
    return [x, z, y]


def build(
    scroll: str,
    out_dir: pathlib.Path,
    seeds_dir: pathlib.Path,
    candidate: pathlib.Path | None = None,
    force: bool = False,
    zoom: float = DEFAULT_ZOOM,
) -> pathlib.Path:
    """Write one project directory and return its path."""
    if scroll not in SCROLLS:
        raise SystemExit(f"unknown scroll {scroll!r}; known: {', '.join(sorted(SCROLLS))}")

    suffix = "roundtrip" if candidate else "manual"
    project_name = f"{scroll}-{suffix}"
    path = out_dir / f"{project_name}.khprj"
    if path.exists() and not force:
        raise SystemExit(
            f"{path} already exists; refusing to overwrite an operator project.\n"
            "Pass --force only if that project holds no unexported drawing."
        )

    fragments = []
    views_frags = {}
    if candidate:
        points = load_controls(candidate)
        created = timestamp()
        fragments.append(
            fragment(f"{scroll}_candidate", points, COLOR_CANDIDATE, created)
        )
        # Inactive: this project exists to check an export, not to edit it.
        views_frags[f"{scroll}_candidate"] = {
            "visible": True,
            "active": False,
            "mesh_visible": True,
        }
        anchor = points
    else:
        anchor = None
        for i, (kind, color) in enumerate(
            (("seed", COLOR_SEED), ("estimated", COLOR_ESTIMATE))
        ):
            guide = seeds_dir / f"{scroll}_umbilicus_{kind}.json"
            if not guide.is_file():
                raise SystemExit(f"missing automatic guide {guide}")
            points = load_controls(guide)
            fragments.append(
                fragment(
                    f"{scroll}_guide_{kind}", points, color, timestamp(offset_s=i)
                )
            )
            # Guides are orientation only. They load hidden and inactive so no
            # automatic control can reach the export by default.
            views_frags[f"{scroll}_guide_{kind}"] = {
                "visible": False,
                "active": False,
                "mesh_visible": True,
            }
            if kind == "estimated" or anchor is None:
                anchor = points
        blank = fragment(f"{scroll}_manual", [], COLOR_MANUAL, timestamp(offset_s=2))
        fragments.append(blank)
        views_frags[f"{scroll}_manual"] = {
            "visible": True,
            "active": True,
            "mesh_visible": True,
        }

    if path.exists():
        shutil.rmtree(path)
        time.sleep(0.2)
    (path / "volumes").mkdir(parents=True)
    (path / "fragments").mkdir()

    created = timestamp()
    (path / "project.json").write_text(
        json.dumps(
            {
                "created": created,
                "modified": created,
                "name": project_name,
                "version": 1.0,
                "voxel_size_um": SCROLLS[scroll]["um"],
            },
            sort_keys=True,
            indent=4,
        ),
        encoding="utf8",
    )
    (path / "volumes" / f"{scroll}.volzarr").write_text(
        json.dumps(
            {
                "khartes_version": "1.0",
                "khartes_created": created,
                "khartes_modified": created,
                "khartes_from_vc_render": False,
                "zarr_dir": stream_url(scroll),
                "max_width": 480,
            },
            indent=4,
        ),
        encoding="utf8",
    )
    (path / "fragments" / "all.json").write_text(
        json.dumps(fragments, indent=4), encoding="utf8"
    )
    (path / "views.json").write_text(
        json.dumps(
            {
                "project": {
                    "cur_volume": scroll,
                    "overlay_volumes": ["", ""],
                    "vol_boxes_visible": False,
                },
                "volumes": {
                    scroll: {
                        "direction": 1,
                        "zoom": zoom,
                        "ijktf": view_position(anchor),
                        "color": "#42ff25",
                        "opacity": 1.0,
                        "colormap_name": "",
                        "colormap_range": [0.0, 1.0],
                        "colormap_is_indicator": False,
                    }
                },
                "fragments": views_frags,
            },
            indent=4,
        ),
        encoding="utf8",
    )
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("scroll", help="scroll id, e.g. PHerc0191")
    ap.add_argument(
        "--out",
        type=pathlib.Path,
        default=DEFAULT_OUT,
        help=f"directory to write the project into (default {DEFAULT_OUT})",
    )
    ap.add_argument(
        "--seeds",
        type=pathlib.Path,
        default=pathlib.Path(__file__).resolve().parent / "seeds",
        help="directory holding the automatic guides",
    )
    ap.add_argument(
        "--candidate",
        type=pathlib.Path,
        help="build the step-6 reimport QC project from this exported candidate",
    )
    ap.add_argument("--force", action="store_true", help="replace an existing project")
    ap.add_argument("--zoom", type=float, default=DEFAULT_ZOOM)
    args = ap.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    path = build(
        args.scroll,
        args.out,
        args.seeds,
        candidate=args.candidate,
        force=args.force,
        zoom=args.zoom,
    )
    print(f"wrote {path}")
    print(f"  stream {stream_url(args.scroll)}")
    if args.candidate:
        print("  reimport QC project: review the full useful z range before approving")
    else:
        print(f"  draw on the active blank fragment {args.scroll}_manual")
        print(f"  export to manual/candidates/{args.scroll}_umbilicus.candidate.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
