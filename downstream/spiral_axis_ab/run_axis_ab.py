"""Prepare and run a hash-bound PHerc1218 production Spiral axis A/B.

The public fitter and inputs are not vendored. This harness verifies their git
pins, creates two datasets that differ only in ``umbilicus.json``, and launches
the merged Villa CLI with an identical configuration for both arms.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Iterable


VILLA_COMMIT = "465cab06084e5587f7aea989440d495318bfb1eb"
PACK_COMMIT = "7116a75521e4f5791a4d077311efb5558bf3e20e"
MANUAL_COMMIT = "57e09a3d6f25773a2e0cad9d21eb97296cef50c8"
Z_BEGIN = 5220
Z_END = 6020
EXPECTED_PATCHES = (
    "seed-z2464-pherc1218",
    "seed-z2688-pherc1218",
    "seed-z2912-pherc1218",
)
PACK_FILES = (
    "abs_winding.json",
    "relative_windings.json",
    "same_windings.json",
)
SCROLL_SPEC = {
    "schema_version": 1,
    "name": "PHerc1218",
    "voxel_size_um": 8.64,
    "spiral_outward_sense": "CW",
    "umbilicus": {"coordinate_scale": 1.0},
    "normal_zarr_group": "2",
    "surf_sdt_zarr_group": "1",
    "lasagna_scale": 2,
    "paths": {},
}


class ExperimentError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ExperimentError(f"cannot read JSON {path}: {exc}") from exc


def git_head(path: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ExperimentError(f"not a readable git checkout: {path}\n{result.stderr}")
    return result.stdout.strip()


def require_commit(path: Path, expected: str, label: str) -> None:
    actual = git_head(path)
    if actual != expected:
        raise ExperimentError(f"{label} is {actual}; expected pinned commit {expected}")


def axis_points(path: Path) -> list[dict[str, float]]:
    document = read_json(path)
    raw = document.get("control_points") if isinstance(document, dict) else None
    if not isinstance(raw, list) or len(raw) < 2:
        raise ExperimentError(f"{path}: control_points must contain at least two points")
    points: list[dict[str, float]] = []
    for index, item in enumerate(raw):
        try:
            point = {key: float(item[key]) for key in ("x", "y", "z")}
        except (KeyError, TypeError, ValueError) as exc:
            raise ExperimentError(f"{path}: invalid control point {index}") from exc
        if not all(math.isfinite(value) for value in point.values()):
            raise ExperimentError(f"{path}: non-finite control point {index}")
        points.append(point)
    zs = [point["z"] for point in points]
    if any(b <= a for a, b in zip(zs, zs[1:])):
        raise ExperimentError(f"{path}: control point z values must strictly increase")
    if zs[0] > Z_BEGIN or zs[-1] < Z_END - 1:
        raise ExperimentError(f"{path}: axis does not cover [{Z_BEGIN}, {Z_END})")
    return points


def interpolate(points: list[dict[str, float]], z: float) -> tuple[float, float]:
    for left, right in zip(points, points[1:]):
        if left["z"] <= z <= right["z"]:
            fraction = (z - left["z"]) / (right["z"] - left["z"])
            return (
                left["x"] + fraction * (right["x"] - left["x"]),
                left["y"] + fraction * (right["y"] - left["y"]),
            )
    raise ExperimentError(f"z={z} falls outside the axis")


def axis_disagreement(first: Path, second: Path) -> dict[str, Any]:
    a = axis_points(first)
    b = axis_points(second)
    rows = []
    for z in range(Z_BEGIN, Z_END):
        ax, ay = interpolate(a, z)
        bx, by = interpolate(b, z)
        rows.append((z, math.hypot(ax - bx, ay - by)))
    ordered = sorted(distance for _, distance in rows)
    peak_z, peak = max(rows, key=lambda item: item[1])
    return {
        "sample_count": len(rows),
        "minimum_voxels": min(ordered),
        "median_voxels": (ordered[399] + ordered[400]) / 2,
        "maximum_voxels": peak,
        "maximum_z": peak_z,
    }


def intersecting_patches(patch_root: Path) -> list[str]:
    selected = []
    for meta in sorted(patch_root.glob("*/meta.json")):
        document = read_json(meta)
        try:
            z0 = float(document["bbox"][0][2])
            z1 = float(document["bbox"][1][2])
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ExperimentError(f"{meta}: invalid bbox") from exc
        if z1 > Z_BEGIN and z0 < Z_END:
            selected.append(meta.parent.name)
    return selected


def file_manifest(root: Path, *, omit: Iterable[str] = ()) -> dict[str, str]:
    omitted = set(omit)
    return {
        path.relative_to(root).as_posix(): sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.relative_to(root).as_posix() not in omitted
    }


def copy_dataset(destination: Path, pack: Path, axis: Path) -> None:
    if destination.exists():
        raise ExperimentError(
            f"refusing to overwrite existing dataset {destination}; use a new --work path"
        )
    destination.mkdir(parents=True)
    for name in PACK_FILES:
        source = pack / name
        if not source.is_file():
            raise ExperimentError(f"missing public pack input: {source}")
        shutil.copy2(source, destination / name)
    patches = pack / "verified_patches"
    if not patches.is_dir():
        raise ExperimentError(f"missing public patch directory: {patches}")
    shutil.copytree(patches, destination / "verified_patches")
    shutil.copy2(axis, destination / "umbilicus.json")
    write_json(destination / "spiral-scroll.json", SCROLL_SPEC)


def prepare(args: argparse.Namespace) -> int:
    work = args.work.resolve()
    villa = args.villa_dir.resolve()
    pack = args.pack_dir.resolve()
    manual_repo = args.manual_repo.resolve()
    pack_repo = pack
    while pack_repo != pack_repo.parent and not (pack_repo / ".git").exists():
        pack_repo = pack_repo.parent
    require_commit(villa, VILLA_COMMIT, "Villa")
    require_commit(pack_repo, PACK_COMMIT, "constraint pack")
    require_commit(manual_repo, MANUAL_COMMIT, "manual-axis repository")

    baseline_axis = pack / "umbilicus.json"
    manual_axis = manual_repo / "PHerc1218_umbilicus.json"
    axis_points(baseline_axis)
    axis_points(manual_axis)

    manifest_path = work / "input_manifest.json"
    if manifest_path.exists():
        verify_prepared(work)
        print(f"prepared inputs already verified: {manifest_path}")
        return 0
    if (work / "datasets").exists():
        raise ExperimentError(
            f"partial dataset state exists at {work / 'datasets'}; use a new --work path"
        )

    baseline_dir = work / "datasets" / "baseline"
    manual_dir = work / "datasets" / "manual"
    copy_dataset(baseline_dir, pack, baseline_axis)
    copy_dataset(manual_dir, pack, manual_axis)

    baseline_non_axis = file_manifest(baseline_dir, omit=("umbilicus.json",))
    manual_non_axis = file_manifest(manual_dir, omit=("umbilicus.json",))
    if baseline_non_axis != manual_non_axis:
        raise ExperimentError("prepared arms differ outside umbilicus.json")
    patches = intersecting_patches(baseline_dir / "verified_patches")
    if tuple(patches) != EXPECTED_PATCHES:
        raise ExperimentError(f"intersecting patches are {patches}; expected {EXPECTED_PATCHES}")

    manifest = {
        "schema_version": 1,
        "created_utc": utc_now(),
        "window_full_resolution_z": [Z_BEGIN, Z_END],
        "sources": {
            "villa": {
                "repository": "https://github.com/ScrollPrize/villa",
                "commit": VILLA_COMMIT,
                "local_path": str(villa),
            },
            "constraint_pack": {
                "repository": "https://github.com/IyanDopico/vesuvius-sheet-tools",
                "commit": PACK_COMMIT,
                "local_path": str(pack),
            },
            "manual_axis": {
                "repository": "https://github.com/AlexeyDrobkovStrikesBack/herculaneum-umbilici",
                "commit": MANUAL_COMMIT,
                "local_path": str(manual_axis),
            },
        },
        "axes": {
            "baseline": {
                "path": str(baseline_dir / "umbilicus.json"),
                "sha256": sha256(baseline_dir / "umbilicus.json"),
                "control_count": len(axis_points(baseline_dir / "umbilicus.json")),
            },
            "manual": {
                "path": str(manual_dir / "umbilicus.json"),
                "sha256": sha256(manual_dir / "umbilicus.json"),
                "control_count": len(axis_points(manual_dir / "umbilicus.json")),
            },
        },
        "axis_disagreement": axis_disagreement(
            baseline_dir / "umbilicus.json", manual_dir / "umbilicus.json"
        ),
        "intersecting_patch_ids": patches,
        "non_axis_inputs": baseline_non_axis,
        "non_axis_manifest_sha256": canonical_hash(baseline_non_axis),
        "only_treatment_difference_verified": True,
    }
    write_json(manifest_path, manifest)
    verify_prepared(work)
    print(json.dumps(manifest["axis_disagreement"], indent=2))
    print(f"prepared and verified: {manifest_path}")
    return 0


def verify_prepared(work: Path) -> dict[str, Any]:
    manifest_path = work / "input_manifest.json"
    manifest = read_json(manifest_path)
    arms = {name: work / "datasets" / name for name in ("baseline", "manual")}
    for name, root in arms.items():
        if not root.is_dir():
            raise ExperimentError(f"missing prepared arm: {root}")
        expected_axis = manifest["axes"][name]["sha256"]
        if sha256(root / "umbilicus.json") != expected_axis:
            raise ExperimentError(f"{name} axis hash changed after preparation")
        axis_points(root / "umbilicus.json")
    first = file_manifest(arms["baseline"], omit=("umbilicus.json",))
    second = file_manifest(arms["manual"], omit=("umbilicus.json",))
    if first != second or canonical_hash(first) != manifest["non_axis_manifest_sha256"]:
        raise ExperimentError("prepared non-axis inputs changed or differ between arms")
    patches = intersecting_patches(arms["baseline"] / "verified_patches")
    if patches != list(EXPECTED_PATCHES):
        raise ExperimentError(f"expected exactly three pinned patches, found {patches}")
    return manifest


def fit_config(steps: int) -> dict[str, Any]:
    if steps <= 0:
        raise ExperimentError("--steps must be positive")
    return {
        "z_begin": Z_BEGIN,
        "z_end": Z_END,
        "optimizer_random_seed": 1,
        "optimizer_num_training_steps": steps,
        # Current main defaults to the asset-backed phase bundle even when its
        # individual weights are zero. grad_mag plus zero weights is the
        # explicit asset-free/PCL-only mode used by this experiment.
        "dense_spacing_mode": "grad_mag",
        "loss_weight_dense_normals": 0.0,
        "loss_weight_dense_spacing": 0.0,
        "loss_weight_dense_spacing_count": 0.0,
        "loss_weight_dense_spacing_density": 0.0,
        "loss_weight_dense_attachment": 0.0,
        "loss_weight_min_spacing": 0.0,
        "loss_weight_shell_outer": 0.0,
        "loss_weight_shell_patch_radius": 0.0,
        "patch_erode_patches": 0,
        # The headless fitter explicitly supports an unresolved outer index;
        # with no shell/dense losses this matches the published PCL-only run
        # and derives the export range from the actual constraints.
        "shell_outer_winding_idx": None,
        "output_first_winding": 0,
        "model_initial_dr_per_winding": 20.0,
        "model_gap_expander_num_windings": 130,
        "sample_count_unattached_pcls_per_step": 800,
        "pcl_stratified_pcl_sampling": False,
        "dt_target_mode": "strip_median",
        "output_save_png_visualizations": True,
    }


def python_environment(python: Path) -> dict[str, Any]:
    code = (
        "import json,platform,torch; "
        "print(json.dumps({'python':platform.python_version(),"
        "'torch':torch.__version__,'cuda':torch.version.cuda,"
        "'cuda_available':torch.cuda.is_available(),"
        "'device':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}))"
    )
    result = subprocess.run(
        [str(python), "-c", code], text=True, capture_output=True, check=False
    )
    if result.returncode:
        raise ExperimentError(f"cannot inspect Python environment:\n{result.stderr}")
    info = json.loads(result.stdout.strip())
    py_version = tuple(int(part) for part in info["python"].split(".")[:2])
    if py_version < (3, 14):
        raise ExperimentError(f"current merged Villa requires Python >=3.14, found {info['python']}")
    match = re.match(r"(\d+)\.(\d+)", info["torch"])
    if not match:
        raise ExperimentError(f"cannot parse torch version {info['torch']!r}")
    torch_version = tuple(map(int, match.groups()))
    if torch_version >= (2, 13):
        raise ExperimentError(
            f"refusing PyTorch {info['torch']}: use 2.12.x to avoid the reported transform.inv VRAM regression"
        )
    if not info["cuda_available"]:
        raise ExperimentError("CUDA is unavailable in the selected Python environment")
    return info


def latest_result(output_root: Path) -> Path | None:
    matches = sorted(
        output_root.rglob("satisfied_fitted.json"),
        key=lambda path: path.stat().st_mtime,
    )
    return matches[-1] if matches else None


def run_one(
    *,
    arm: str,
    phase: str,
    work: Path,
    villa: Path,
    python: Path,
    config: dict[str, Any],
    environment_info: dict[str, Any],
) -> dict[str, Any]:
    phase_root = work / "runs" / phase
    receipt_path = phase_root / f"{arm}_receipt.json"
    if receipt_path.exists():
        receipt = read_json(receipt_path)
        if receipt.get("status") == "passed":
            print(f"{phase}/{arm}: existing passed receipt; skipping")
            return receipt
        raise ExperimentError(f"existing non-passed receipt at {receipt_path}; use a new phase/work path")

    spiral_dir = villa / "volume-cartographer" / "scripts" / "spiral"
    fit_script = spiral_dir / "fit_spiral.py"
    cli_adapter = Path(__file__).with_name("fit_cli_adapter.py").resolve()
    if not fit_script.is_file():
        raise ExperimentError(f"missing merged fitter: {fit_script}")
    if not cli_adapter.is_file():
        raise ExperimentError(f"missing CLI path-resolution adapter: {cli_adapter}")
    dataset = work / "datasets" / arm
    output_root = work / "outputs" / phase / arm
    cache = work / "cache" / phase / arm
    log_path = phase_root / f"{arm}.log"
    output_root.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    phase_root.mkdir(parents=True, exist_ok=True)

    command = [
        str(python),
        str(cli_adapter),
        str(fit_script),
        "--dataset",
        str(dataset),
        "--cache",
        str(cache),
    ]
    env = dict(os.environ)
    env.update(
        {
            "WANDB_MODE": "disabled",
            "FIT_SPIRAL_OUT_DIR": str(output_root),
            "FIT_SPIRAL_CACHE_DIR": str(cache),
            "FIT_SPIRAL_RUN_TAG": f"pherc1218-axis-ab-{phase}-{arm}",
            "FIT_SPIRAL_CONFIG_OVERRIDES": json.dumps(config, sort_keys=True),
            "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
        }
    )
    started = utc_now()
    started_clock = time.monotonic()
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "status": "running",
        "arm": arm,
        "phase": phase,
        "started_utc": started,
        "command": command,
        "villa_commit": VILLA_COMMIT,
        "cli_adapter_sha256": sha256(cli_adapter),
        "axis_sha256": sha256(dataset / "umbilicus.json"),
        "config": config,
        "config_sha256": canonical_hash(config),
        "environment": environment_info,
        "log": str(log_path),
    }
    write_json(receipt_path, receipt)

    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            cwd=spiral_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(f"[{arm}] {line}", end="", flush=True)
            log.write(line)
        return_code = process.wait()

    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    patch_matches = re.findall(r"fitting\s+(\d+)\s+patches", log_text)
    patch_count = int(patch_matches[-1]) if patch_matches else None
    result_path = latest_result(output_root)
    receipt.update(
        {
            "finished_utc": utc_now(),
            "elapsed_seconds": time.monotonic() - started_clock,
            "return_code": return_code,
            "intersecting_patch_count_from_log": patch_count,
            "result_path": str(result_path) if result_path else None,
            "result_sha256": sha256(result_path) if result_path else None,
        }
    )
    receipt["status"] = (
        "passed"
        if return_code == 0 and patch_count == len(EXPECTED_PATCHES) and result_path
        else "failed"
    )
    write_json(receipt_path, receipt)
    if receipt["status"] != "passed":
        raise ExperimentError(
            f"{phase}/{arm} failed admission: return={return_code}, patches={patch_count}, result={result_path}"
        )
    return receipt


def run_pair(args: argparse.Namespace) -> int:
    work = args.work.resolve()
    villa = args.villa_dir.resolve()
    python = args.python.resolve()
    require_commit(villa, VILLA_COMMIT, "Villa")
    manifest = verify_prepared(work)
    environment_info = python_environment(python)
    config = fit_config(args.steps)
    phase_root = work / "runs" / args.phase
    pair_path = phase_root / "pair_config.json"
    pair = {
        "schema_version": 1,
        "created_utc": utc_now(),
        "phase": args.phase,
        "scientific_evidence": args.phase == "full" and args.steps == 30000,
        "config": config,
        "config_sha256": canonical_hash(config),
        "cli_adapter_sha256": sha256(
            Path(__file__).with_name("fit_cli_adapter.py").resolve()
        ),
        "input_manifest_sha256": sha256(work / "input_manifest.json"),
        "environment": environment_info,
        "arm_order": ["baseline", "manual"],
    }
    if pair_path.exists():
        existing = read_json(pair_path)
        comparable = {key: value for key, value in pair.items() if key != "created_utc"}
        previous = {key: value for key, value in existing.items() if key != "created_utc"}
        if comparable != previous:
            raise ExperimentError(f"phase {args.phase!r} was already frozen with a different pair config")
    else:
        write_json(pair_path, pair)

    receipts = [
        run_one(
            arm=arm,
            phase=args.phase,
            work=work,
            villa=villa,
            python=python,
            config=config,
            environment_info=environment_info,
        )
        for arm in ("baseline", "manual")
    ]
    if len({item["config_sha256"] for item in receipts}) != 1:
        raise ExperimentError("arm receipts do not have identical configurations")
    if len({item["environment"]["device"] for item in receipts}) != 1:
        raise ExperimentError("arm receipts were not produced on the same GPU")
    summary = {
        "schema_version": 1,
        "phase": args.phase,
        "status": "passed",
        "scientific_evidence": pair["scientific_evidence"],
        "only_treatment_difference_verified": manifest["only_treatment_difference_verified"],
        "receipts": [str(phase_root / f"{arm}_receipt.json") for arm in ("baseline", "manual")],
    }
    write_json(phase_root / "pair_receipt.json", summary)
    print(json.dumps(summary, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare", help="freeze and hash both input arms")
    prepare_parser.add_argument("--work", type=Path, required=True)
    prepare_parser.add_argument("--villa-dir", type=Path, required=True)
    prepare_parser.add_argument("--pack-dir", type=Path, required=True)
    prepare_parser.add_argument("--manual-repo", type=Path, required=True)
    prepare_parser.set_defaults(func=prepare)

    run_parser = subparsers.add_parser("run", help="run the pinned pair sequentially")
    run_parser.add_argument("--work", type=Path, required=True)
    run_parser.add_argument("--villa-dir", type=Path, required=True)
    run_parser.add_argument("--python", type=Path, required=True)
    run_parser.add_argument(
        "--phase", choices=("smoke", "smoke-resolved", "full"), required=True
    )
    run_parser.add_argument("--steps", type=int, required=True)
    run_parser.set_defaults(func=run_pair)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ExperimentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
