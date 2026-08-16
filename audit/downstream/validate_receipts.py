#!/usr/bin/env python3
"""Validate archived downstream-cross-annotation JSON receipts without network."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


def close(a, b, atol=1e-12):
    return math.isclose(float(a), float(b), rel_tol=0.0, abs_tol=atol)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mean(values):
    return sum(values) / len(values)


def median(values):
    values = sorted(values)
    n = len(values)
    return values[n // 2] if n % 2 else (values[n // 2 - 1] + values[n // 2]) / 2


def validate_axis(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema"] == "downstream-cross-annotation-axis-q-archived-v1"
    all_delta = []
    all_wins = 0
    for scroll in data["screen6"]["scrolls"]:
        rows = scroll["rows"]
        public = [r["public_q"] for r in rows]
        ours = [r["ours_q"] for r in rows]
        delta = [a - b for a, b in zip(ours, public)]
        summary = scroll["summary"]
        assert summary["n"] == len(rows) == 6
        assert close(summary["public_mean"], mean(public))
        assert close(summary["ours_mean"], mean(ours))
        assert close(summary["ours_minus_public_mean"], mean(delta))
        assert summary["ours_wins"] == sum(d > 0 for d in delta)
        all_delta.extend(delta)
        all_wins += sum(d > 0 for d in delta)
    pooled = data["screen6"]["pooled_descriptive_only"]
    assert pooled["n"] == len(all_delta) == 36
    assert close(pooled["ours_minus_public_mean"], mean(all_delta))
    assert close(pooled["ours_minus_public_median"], median(all_delta))
    assert pooled["ours_wins"] == all_wins

    full = data["pherc0813_full30"]
    rows = full["rows"]
    assert len(rows) == 30
    public = [r["public_q"] for r in rows]
    ours = [r["ours_q"] for r in rows]
    eye = [r["posthoc_eye_q"] for r in rows]
    d_ours = [a - b for a, b in zip(ours, public)]
    d_eye = [a - b for a, b in zip(eye, public)]
    s = full["summary"]
    checks = {
        "public_mean": mean(public), "public_median": median(public),
        "ours_mean": mean(ours), "ours_median": median(ours),
        "posthoc_eye_mean": mean(eye), "posthoc_eye_median": median(eye),
        "ours_minus_public_mean": mean(d_ours),
        "ours_minus_public_median": median(d_ours),
        "posthoc_eye_minus_public_mean": mean(d_eye),
    }
    for key, value in checks.items():
        assert close(s[key], value), (key, s[key], value)
    assert s["ours_wins"] == sum(d > 0 for d in d_ours)
    assert s["posthoc_eye_wins"] == sum(d > 0 for d in d_eye)
    assert s["posthoc_eye_ties"] == sum(d == 0 for d in d_eye)


def validate_order(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema"] == "downstream-cross-annotation-order-v1"
    assert len(data["scrolls"]) == 3
    for scroll in data["scrolls"]:
        for row in scroll["pairwise"]:
            n = row["n_pairs"]
            cross = row["cross"]
            assert sum(cross.values()) == n
            for name in row["axes"]:
                score = row[name]
                assert close(score["fraction"], score["kept"] / n)
        strict = scroll["strict_three_axis"]
        n = strict["n_pairs"]
        assert sum(strict["public_vs_ours_cross"].values()) == n
        for score in strict["scores"].values():
            assert close(score["fraction"], score["kept"] / n)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("directory", nargs="?", type=Path,
                    default=Path(__file__).resolve().parent)
    args = ap.parse_args()
    order = args.directory / "results_order_fixtures_20260816.json"
    axis = args.directory / "results_axis_q_20260816.json"
    validate_order(order)
    validate_axis(axis)
    print(f"PASS {order.name} sha256={file_hash(order)}")
    print(f"PASS {axis.name} sha256={file_hash(axis)}")


if __name__ == "__main__":
    main()
