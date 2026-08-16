#!/usr/bin/env python3
"""Compare public, independent, and auto axes on shipped neutral-tracing fixtures.

This is a read-only extension of herculaneum-umbilici/scripts/order_stat.py.
It does not retrace CT imagery.  For every track pair it requires all compared
axes to return a radial-order sign on at least three identical heights.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

EXPECTED_EXTERNAL = "57e09a3d6f25773a2e0cad9d21eb97296cef50c8"
EXPECTED_OURS = "3a1d8aa1811f6f1428e76513feeabb50535e56d2"
SCROLLS = ("PHerc0191", "PHerc0358", "PHerc1203")
L0_TO_L3 = 8.0
VOXEL_UM = 9.362


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def portable_path(path: Path, roots: tuple[tuple[Path, str], ...]) -> str:
    """Return a stable receipt path without exposing a runner's local directory."""
    resolved = path.resolve()
    for root, label in roots:
        try:
            relative = resolved.relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
        return f"{label}/{relative}" if label else relative
    return f"external-input/{path.name}"


def git_head(path: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=path, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def paths_match_commit(repo: Path, commit: str, paths: list[str]) -> bool:
    """True when tracked/working copies of `paths` are unchanged since commit."""
    try:
        return subprocess.run(
            ["git", "diff", "--quiet", commit, "--", *paths], cwd=repo
        ).returncode == 0
    except OSError:
        return False


def load_order_module(external: Path):
    path = external / "scripts" / "order_stat.py"
    spec = importlib.util.spec_from_file_location("public_order_stat", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def axis_from_json(path: Path, zs: np.ndarray) -> np.ndarray:
    points = sorted(json.loads(path.read_text(encoding="utf-8"))["control_points"],
                    key=lambda p: p["z"])
    pz = np.asarray([p["z"] for p in points], dtype=float)
    x = np.interp(zs, pz, [p["x"] / L0_TO_L3 for p in points])
    y = np.interp(zs, pz, [p["y"] / L0_TO_L3 for p in points])
    return np.column_stack((x, y))


def preserved(signs: dict[int, int]) -> bool:
    return len(set(signs.values())) == 1


def pairwise(records, left: str, right: str, min_common: int) -> dict:
    qualified = []
    for signs in records:
        common = sorted(set(signs[left]) & set(signs[right]))
        if len(common) >= min_common:
            qualified.append((
                preserved({i: signs[left][i] for i in common}),
                preserved({i: signs[right][i] for i in common}),
            ))
    n = len(qualified)
    lk = sum(x for x, _ in qualified)
    rk = sum(y for _, y in qualified)
    return {
        "axes": [left, right],
        "n_pairs": n,
        left: {"kept": lk, "fraction": lk / n if n else None},
        right: {"kept": rk, "fraction": rk / n if n else None},
        "cross": {
            "both": sum(x and y for x, y in qualified),
            f"{left}_only": sum(x and not y for x, y in qualified),
            f"{right}_only": sum(y and not x for x, y in qualified),
            "neither": sum(not x and not y for x, y in qualified),
        },
    }


def strict_three(records, names: tuple[str, ...], min_common: int) -> dict:
    qualified = []
    for signs in records:
        common = set(signs[names[0]])
        for name in names[1:]:
            common &= set(signs[name])
        common = sorted(common)
        if len(common) >= min_common:
            qualified.append({
                name: preserved({i: signs[name][i] for i in common})
                for name in names
            })
    n = len(qualified)
    out = {"axes": list(names), "n_pairs": n, "scores": {}}
    for name in names:
        kept = sum(q[name] for q in qualified)
        out["scores"][name] = {
            "kept": kept,
            "fraction": kept / n if n else None,
        }
    out["public_vs_ours_cross"] = {
        "both": sum(q["public"] and q["ours"] for q in qualified),
        "public_only": sum(q["public"] and not q["ours"] for q in qualified),
        "ours_only": sum(q["ours"] and not q["public"] for q in qualified),
        "neither": sum(not q["public"] and not q["ours"] for q in qualified),
    }
    return out


def compare_scroll(scroll: str, external: Path, ours_dir: Path, order) -> dict:
    fixture = external / "qc" / f"order_fixture_{scroll}.npz"
    public_json = external / f"{scroll}_umbilicus.json"
    ours_json = ours_dir / f"{scroll}_umbilicus.json"
    z, tracks = order.load(str(fixture))
    axes = {
        "public": z["man_c"],
        "ours": axis_from_json(ours_json, z["slice_z"]),
        "auto": z["auto_c"],
    }
    public_rebuilt = axis_from_json(public_json, z["slice_z"])
    residual = np.linalg.norm(public_rebuilt - z["man_c"], axis=1)
    if float(residual.max()) > 1e-9:
        raise RuntimeError(f"{scroll}: public coordinate reconstruction drift")

    records = []
    for a in range(len(tracks)):
        for b in range(a + 1, len(tracks)):
            common = sorted(set(tracks[a]) & set(tracks[b]))
            if len(common) < 2:
                continue
            signs = {name: {} for name in axes}
            for i in common:
                pa, pb = tracks[a][i], tracks[b][i]
                for name, centres in axes.items():
                    value = order.radial_sign(pa, pb, centres[i])
                    if value is not None:
                        signs[name][i] = value
            records.append(signs)

    separation_mm = (
        np.linalg.norm(axes["public"] - axes["ours"], axis=1)
        * L0_TO_L3 * VOXEL_UM / 1000.0
    )
    receipt_roots = (
        (external, "herculaneum-umbilici"),
        (ours_dir.parent, ""),
    )
    return {
        "scroll": scroll,
        "fixture": {
            "path": portable_path(fixture, receipt_roots),
            "sha256": sha256(fixture),
            "n_tracks": len(tracks),
            "n_heights": int(len(z["slice_z"])),
            "z_min": int(z["slice_z"].min()),
            "z_max": int(z["slice_z"].max()),
        },
        "inputs": {
            "public": {
                "path": portable_path(public_json, receipt_roots),
                "sha256": sha256(public_json),
            },
            "ours": {
                "path": portable_path(ours_json, receipt_roots),
                "sha256": sha256(ours_json),
            },
        },
        "public_fixture_reconstruction_max_l3_px": float(residual.max()),
        "public_ours_separation_mm": {
            "median": float(np.median(separation_mm)),
            "min": float(separation_mm.min()),
            "max": float(separation_mm.max()),
        },
        "pairwise": [
            pairwise(records, "public", "ours", order.MIN_COMMON),
            pairwise(records, "public", "auto", order.MIN_COMMON),
            pairwise(records, "ours", "auto", order.MIN_COMMON),
        ],
        "strict_three_axis": strict_three(
            records, ("public", "ours", "auto"), order.MIN_COMMON
        ),
    }


def main() -> None:
    workspace = Path(__file__).resolve().parents[3]
    ap = argparse.ArgumentParser()
    ap.add_argument("--external", type=Path,
                    default=workspace / "_external" / "herculaneum-umbilici")
    ap.add_argument("--ours-dir", type=Path,
                    default=workspace / "umbilicus13" / "manual")
    ap.add_argument("--ours-repo", type=Path, default=workspace / "umbilicus13")
    ap.add_argument("--scrolls", nargs="+", choices=SCROLLS, default=list(SCROLLS))
    ap.add_argument("--output", type=Path)
    ap.add_argument("--allow-source-drift", action="store_true")
    args = ap.parse_args()

    heads = {"external": git_head(args.external), "ours": git_head(args.ours_repo)}
    expected = {"external": EXPECTED_EXTERNAL, "ours": EXPECTED_OURS}
    if not args.allow_source_drift:
        if heads["external"] != expected["external"]:
            raise SystemExit(
                f"external HEAD {heads['external']!r} != pinned {expected['external']}"
            )
        curve_paths = [f"manual/{s}_umbilicus.json" for s in args.scrolls]
        if not paths_match_commit(args.ours_repo, expected["ours"], curve_paths):
            raise SystemExit(
                "independent curve bytes differ from their pinned producing commit; "
                "use --allow-source-drift only after reviewing the diff"
            )

    order = load_order_module(args.external)
    receipt = {
        "schema": "downstream-cross-annotation-order-v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "claim_boundary": (
            "Neutral-tracing fixture arithmetic; not ground truth. The fixture tracer "
            "is not shipped and the public report documents pipeline dependence."
        ),
        "source_heads": heads,
        "expected_heads": expected,
        "parameters": {
            "bin_deg": order.BIN_DEG,
            "min_bins": order.MIN_BINS,
            "dominance": order.DOMINANCE,
            "min_common_heights": order.MIN_COMMON,
            "l0_to_l3": L0_TO_L3,
            "voxel_um": VOXEL_UM,
        },
        "scrolls": [compare_scroll(s, args.external, args.ours_dir, order)
                    for s in args.scrolls],
    }
    raw = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
        print(args.output)
    else:
        sys.stdout.write(raw)


if __name__ == "__main__":
    main()
