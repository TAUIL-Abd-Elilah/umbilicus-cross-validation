#!/usr/bin/env python3
"""Read-only CT radial-anisotropy comparison for independent umbilicus curves.

The primary q implementation is imported unchanged from the public
herculaneum-umbilici repository. CT z-planes are streamed anonymously and
discarded. No cache or image file is created. This is an exploratory extension,
not a new pre-registered accuracy experiment and not ground truth.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import platform
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

EXPECTED_EXTERNAL = "57e09a3d6f25773a2e0cad9d21eb97296cef50c8"
EXPECTED_OURS = "3a1d8aa1811f6f1428e76513feeabb50535e56d2"
EXPECTED_VILLA = "94ba215963afb6216e380fe2c86131fa5e724c3b"
LEVEL = 1
SUB = 2
R0_FRAC = 0.25
RING_FRAC = 0.95
R_MAX, R_MIN, R_STEP = 2000, 400, 25

VOLUMES = {
    "PHerc0191": "20250821151635-9.362um-1.2m-113keV-masked.zarr",
    "PHerc0257": "20250821151750-9.362um-1.2m-113keV-masked.zarr",
    "PHerc0358": "20250821151737-9.362um-1.2m-113keV-masked.zarr",
    "PHerc0800": "20250521135224-8.640um-1.2m-116keV-masked.zarr",
    "PHerc0813": "20250821151723-9.362um-1.2m-113keV-masked.zarr",
    "PHerc1203": "20250820131727-9.362um-1.2m-113keV-masked.zarr",
}

FULL_Z = {
    "PHerc0191": [3496,3992,4488,4984,5480,5976,6472,6968,7464,7960,8456,8952,9448,9944,10440,10936,11432,11928,12424,12920,13416,13912,14408,14904,15400,15896,16392,16888,17384,17880],
    "PHerc0257": [2888,3380,3872,4366,4858,5350,5844,6336,6830,7322,7814,8308,8800,9292,9786,10278,10770,11264,11756,12248,12742,13234,13726,14220,14712,15204,15698,16190,16682,17176],
    "PHerc0358": [1768,2152,2536,2922,3306,3690,4074,4460,4844,5228,5614,5998,6382,6766,7152,7536,7920,8304,8690,9074,9458,9844,10228,10612,10996,11382,11766,12150,12534,12920],
    "PHerc0800": [4256,4824,5394,5962,6532,7102,7670,8240,8808,9378,9946,10516,11084,11654,12222,12792,13362,13930,14500,15068,15638,16206,16776,17344,17914,18484,19052,19622,20190,20760],
    "PHerc0813": [2600,3062,3524,3984,4446,4908,5370,5832,6294,6756,7218,7680,8142,8602,9064,9526,9988,10450,10912,11374,11836,12298,12758,13220,13682,14144,14606,15068,15530,15992],
    "PHerc1203": [2320,2854,3390,3926,4460,4996,5530,6066,6600,7136,7672,8206,8742,9276,9812,10348,10882,11418,11952,12488,13022,13558,14094,14628,15164,15698,16234,16770,17304,17840],
}
SCREEN_INDEX = (0, 5, 10, 15, 20, 25)


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


def import_public_measure(external: Path, villa: Path):
    measure = external / "axis_benefit" / "measure"
    spiral = villa / "volume-cartographer" / "scripts" / "spiral"
    sys.path[:0] = [str(measure), str(spiral)]
    import axisdemo as axis  # type: ignore
    import tiled_st  # type: ignore
    import zslice_http  # type: ignore
    return axis, tiled_st, zslice_http


def common_outer_radius(axis, inside: np.ndarray, centres) -> float | None:
    for radius in range(R_MAX, R_MIN - 1, -R_STEP):
        if all(axis.ring_inside_fraction(inside, c, radius) >= RING_FRAC
               for c in centres):
            return float(radius)
    return None


def summarize(rows: list[dict], candidate_names: list[str]) -> dict:
    valid = [r for r in rows if all(r.get("q", {}).get(n) is not None
                                    for n in candidate_names)]
    out = {"n_valid": len(valid), "axes": {}}
    for name in candidate_names:
        values = np.asarray([r["q"][name] for r in valid], dtype=float)
        out["axes"][name] = {
            "mean": float(values.mean()) if len(values) else None,
            "median": float(np.median(values)) if len(values) else None,
            "min": float(values.min()) if len(values) else None,
            "max": float(values.max()) if len(values) else None,
        }
    public = np.asarray([r["q"]["public"] for r in valid], dtype=float)
    out["comparisons"] = {}
    for name in candidate_names:
        if name == "public":
            continue
        values = np.asarray([r["q"][name] for r in valid], dtype=float)
        delta = values - public
        out["comparisons"][f"{name}_minus_public"] = {
            "mean": float(delta.mean()) if len(delta) else None,
            "median": float(np.median(delta)) if len(delta) else None,
            "wins": int((delta > 0).sum()),
            "ties": int((delta == 0).sum()),
            "n": int(len(delta)),
        }
    return out


def main() -> None:
    workspace = Path(__file__).resolve().parents[3]
    ap = argparse.ArgumentParser()
    ap.add_argument("--protocol", required=True,
                    choices=("screen6", "full-pherc0813", "known-bad-pherc0813"))
    ap.add_argument("--external", type=Path,
                    default=workspace / "_external" / "herculaneum-umbilici")
    ap.add_argument("--ours-repo", type=Path, default=workspace / "umbilicus13")
    ap.add_argument("--ours-dir", type=Path,
                    default=workspace / "umbilicus13" / "manual")
    ap.add_argument(
        "--curve-override",
        type=Path,
        help="Use this curve for a single --scroll run (requires --allow-source-drift).",
    )
    ap.add_argument("--villa", type=Path, default=workspace / "villa")
    ap.add_argument("--scrolls", nargs="+", choices=tuple(VOLUMES))
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--replication-tolerance", type=float, default=1e-6)
    ap.add_argument("--allow-source-drift", action="store_true")
    ap.add_argument("--confirm-network", action="store_true",
                    help="Required: acknowledge anonymous public-CT streaming.")
    args = ap.parse_args()
    if not args.confirm_network:
        raise SystemExit("refusing network run without --confirm-network")

    heads = {
        "external": git_head(args.external),
        "ours": git_head(args.ours_repo),
        "villa": git_head(args.villa),
    }
    expected = {
        "external": EXPECTED_EXTERNAL,
        "ours": EXPECTED_OURS,
        "villa": EXPECTED_VILLA,
    }
    if not args.allow_source_drift:
        for name in ("external", "villa"):
            if heads[name] != expected[name]:
                raise SystemExit(
                    f"{name} HEAD {heads[name]!r} != pinned {expected[name]}"
                )

    axis, tiled_st, zslice_http = import_public_measure(args.external, args.villa)
    if args.protocol == "screen6":
        scrolls = args.scrolls or list(VOLUMES)
        zmap = {s: [FULL_Z[s][i] for i in SCREEN_INDEX] for s in scrolls}
    elif args.protocol == "full-pherc0813":
        scrolls = ["PHerc0813"]
        zmap = {"PHerc0813": FULL_Z["PHerc0813"]}
    else:
        scrolls = ["PHerc0813"]
        zmap = {"PHerc0813": [6616, 9296]}

    curve_paths = [f"manual/{s}_umbilicus.json" for s in scrolls]
    if (not args.allow_source_drift and
            not paths_match_commit(args.ours_repo, expected["ours"], curve_paths)):
        raise SystemExit(
            "independent curve bytes differ from their pinned producing commit; "
            "review before using --allow-source-drift"
        )

    receipt = {
        "schema": "downstream-cross-annotation-axis-q-v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol": args.protocol,
        "claim_boundary": (
            "Exploratory proxy comparison. q measures radial structure-tensor "
            "alignment, not true umbilicus error; slices within a scroll are correlated."
        ),
        "source_heads": heads,
        "expected_heads": expected,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
        },
        "parameters": {
            "level": LEVEL,
            "sub": SUB,
            "ring_fraction": RING_FRAC,
            "radius_sweep": [R_MAX, R_MIN, R_STEP],
            "r0_fraction": R0_FRAC,
            "sigma_d": 1.5,
            "sigma_t": 6.0,
            "sampling": zmap,
        },
        "scrolls": [],
    }
    t_all = time.time()
    receipt_roots = (
        (args.external, "herculaneum-umbilici"),
        (args.ours_repo, ""),
    )
    for scroll in scrolls:
        public_json = args.external / f"{scroll}_umbilicus.json"
        ours_json = (
            args.curve_override
            if args.curve_override is not None
            else args.ours_dir / f"{scroll}_umbilicus.json"
        )
        candidates = {
            "public": public_json,
            "ours": ours_json,
        }
        if scroll == "PHerc0813" and args.protocol != "screen6":
            candidates["posthoc_eye"] = (
                args.external / "axis_benefit" / "PHerc0813_posthoc_eye.json"
            )
        candidate_names = list(candidates)
        functions = {name: axis.villa_axis(str(path), LEVEL)
                     for name, path in candidates.items()}
        public_stick = axis.stick_from_mean(str(public_json), LEVEL)
        shipped = json.loads((args.external / "axis_benefit" /
                              f"prereg_{scroll}.json").read_text(encoding="utf-8"))
        shipped_by_z = {int(r["z_L0"]): r for r in shipped["slices"]}
        volume_root = (
            f"vesuvius-challenge-open-data/{scroll}/volumes/{VOLUMES[scroll]}"
        )
        zs = zmap[scroll]
        rows = []
        pool = ThreadPoolExecutor(1)
        nxt = pool.submit(zslice_http.read_zslice, volume_root, LEVEL,
                          zs[0] // 2, args.workers)
        for index, z0 in enumerate(zs):
            t0 = time.time()
            image = nxt.result()
            if index + 1 < len(zs):
                nxt = pool.submit(zslice_http.read_zslice, volume_root, LEVEL,
                                  zs[index + 1] // 2, args.workers)
            inside = image > 0
            centres = {name: np.asarray(fn(z0 // 2), dtype=float)
                       for name, fn in functions.items()}
            public_mean_stick = np.asarray(public_stick(z0 // 2), dtype=float)
            volume_centre = np.asarray([image.shape[0] / 2, image.shape[1] / 2])
            radius = common_outer_radius(axis, inside, centres.values())
            original_radius = common_outer_radius(
                axis, inside,
                [centres["public"], public_mean_stick, volume_centre],
            )
            row = {
                "index": index,
                "z_l0": z0,
                "z_level": z0 // 2,
                "symmetric_radius": radius,
                "original_radius": original_radius,
                "centres_yx_level1": {
                    name: [float(v) for v in centre]
                    for name, centre in centres.items()
                },
                "q": {},
            }
            tensor = tiled_st.structure_tensor_tiled(
                image, sigma_d=1.5, sigma_t=6.0, sub=SUB
            )
            inside_sub = inside[::SUB, ::SUB]

            def score(centre, r):
                q, n_pixels, sector_fraction = axis.radial_anisotropy_sectored(
                    tensor, inside_sub, centre / SUB,
                    round(R0_FRAC * r) / SUB, r / SUB,
                )
                return {
                    "q": None if not np.isfinite(q) else float(q),
                    "n_pixels": int(n_pixels),
                    "valid_sector_fraction": float(sector_fraction),
                    "ring_fraction": float(axis.ring_inside_fraction(inside, centre, r)),
                }

            if radius is not None:
                for name, centre in centres.items():
                    scored = score(centre, radius)
                    row["q"][name] = scored.pop("q")
                    row.setdefault("diagnostics", {})[name] = scored
            if original_radius is not None:
                original = score(centres["public"], original_radius)["q"]
                row["public_q_original_protocol"] = original
                shipped_row = shipped_by_z.get(z0)
                if shipped_row is not None:
                    shipped_q = shipped_row.get("conditions", {}).get(
                        "annotated", {}).get("q")
                    row["public_q_shipped"] = shipped_q
                    if original is not None and shipped_q is not None:
                        row["replication_abs_error"] = abs(original - float(shipped_q))
                        if row["replication_abs_error"] > args.replication_tolerance:
                            raise RuntimeError(
                                f"{scroll} z{z0}: q replication drift "
                                f"{row['replication_abs_error']}"
                            )
            row["elapsed_seconds"] = time.time() - t0
            rows.append(row)
            print(
                f"{scroll} {index + 1}/{len(zs)} z{z0} "
                + " ".join(f"{n}={row['q'].get(n)}" for n in candidate_names),
                file=sys.stderr, flush=True,
            )
            del image, inside, tensor, inside_sub
            gc.collect()
        pool.shutdown()
        errors = [r["replication_abs_error"] for r in rows
                  if "replication_abs_error" in r]
        receipt["scrolls"].append({
            "scroll": scroll,
            "volume_root": volume_root,
            "inputs": {name: {
                           "path": portable_path(path, receipt_roots),
                           "sha256": sha256(path),
                       }
                        for name, path in candidates.items()},
            "rows": rows,
            "summary": summarize(rows, candidate_names),
            "replication": {
                "n": len(errors),
                "max_abs_error": max(errors) if errors else None,
                "median_abs_error": float(np.median(errors)) if errors else None,
            },
        })
    receipt["wall_seconds"] = time.time() - t_all
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
