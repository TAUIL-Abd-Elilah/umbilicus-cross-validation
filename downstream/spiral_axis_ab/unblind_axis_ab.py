"""Fail-closed review recording and unblinding for the PHerc1218 axis A/B."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Any

from evaluate_axis_ab import (
    FORMAT,
    FROZEN_PLANES,
    canonical_json,
    load_json,
    sha256_file,
)


REVIEW_FORMAT = f"{FORMAT}-blind-review-v1"
PREFERENCES = {"A", "B", "tie", "unusable"}
CONFIDENCES = {"low", "medium", "high"}


class ReviewError(RuntimeError):
    pass


def _aware_timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def make_template(manifest: dict[str, Any], manifest_sha256: str) -> dict[str, Any]:
    if manifest.get("format") != FORMAT:
        raise ReviewError(f"unexpected blind manifest format: {manifest.get('format')!r}")
    if manifest.get("frozen_planes_l0") != list(FROZEN_PLANES):
        raise ReviewError("blind manifest does not contain the seven frozen planes")
    return {
        "format": REVIEW_FORMAT,
        "blind_manifest_sha256": manifest_sha256,
        "reviewer": "",
        "completed_utc": "",
        "attestation": {
            "identity_key_opened_before_completion": None,
            "reviewed_only_blind_assets": None,
        },
        "planes": [
            {
                "z_l0": plane,
                "preference": "",
                "confidence": "",
                "reason": "",
            }
            for plane in FROZEN_PLANES
        ],
        "global_notes": "",
    }


def validate_review(value: dict[str, Any]) -> dict[str, Any]:
    if value.get("format") != REVIEW_FORMAT:
        raise ReviewError(f"unexpected review format: {value.get('format')!r}")
    if not isinstance(value.get("blind_manifest_sha256"), str):
        raise ReviewError("review is not bound to a blind manifest hash")
    if not isinstance(value.get("reviewer"), str) or not value["reviewer"].strip():
        raise ReviewError("reviewer must be recorded before unblinding")
    if not _aware_timestamp(value.get("completed_utc")):
        raise ReviewError("completed_utc must be an ISO-8601 timestamp with timezone")
    attestation = value.get("attestation")
    if not isinstance(attestation, dict):
        raise ReviewError("review attestation is missing")
    if attestation.get("identity_key_opened_before_completion") is not False:
        raise ReviewError("reviewer must attest that the identity key remained closed")
    if attestation.get("reviewed_only_blind_assets") is not True:
        raise ReviewError("reviewer must attest that only blind assets were reviewed")

    rows = value.get("planes")
    if not isinstance(rows, list) or [row.get("z_l0") for row in rows] != list(
        FROZEN_PLANES
    ):
        raise ReviewError("review must contain each frozen plane once and in order")
    for row in rows:
        plane = row["z_l0"]
        if row.get("preference") not in PREFERENCES:
            raise ReviewError(f"z={plane}: invalid or missing preference")
        if row.get("confidence") not in CONFIDENCES:
            raise ReviewError(f"z={plane}: invalid or missing confidence")
        reason = row.get("reason")
        if not isinstance(reason, str) or len(reason.strip()) < 8:
            raise ReviewError(f"z={plane}: record a substantive blind-review reason")
    return value


def validate_assignment(key: dict[str, Any]) -> dict[str, str]:
    if key.get("format") != FORMAT:
        raise ReviewError(f"unexpected private-key format: {key.get('format')!r}")
    assignment = key.get("assignment")
    if not isinstance(assignment, dict):
        raise ReviewError("private key has no assignment")
    if set(assignment) != {"A", "B"} or set(assignment.values()) != {
        "baseline",
        "manual",
    }:
        raise ReviewError(f"invalid private assignment: {assignment!r}")
    return assignment


def unblind_rows(
    rows: list[dict[str, Any]], assignment: dict[str, str]
) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        preference = row["preference"]
        result.append(
            {
                **row,
                "preferred_arm": assignment[preference]
                if preference in {"A", "B"}
                else preference,
            }
        )
    return result


def initialize(args: argparse.Namespace) -> int:
    evaluation = args.evaluation.resolve(strict=True)
    manifest_path = evaluation / "blind" / "manifest.json"
    manifest = load_json(manifest_path, "blind manifest")
    template = make_template(manifest, sha256_file(manifest_path))
    review_path = args.review.resolve()
    if review_path.exists():
        raise ReviewError(f"refusing to overwrite existing review: {review_path}")
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_bytes(canonical_json(template))
    print(f"wrote blind review template: {review_path}")
    return 0


def unblind(args: argparse.Namespace) -> int:
    evaluation = args.evaluation.resolve(strict=True)
    manifest_path = evaluation / "blind" / "manifest.json"
    manifest = load_json(manifest_path, "blind manifest")
    review_path = args.review.resolve(strict=True)

    # This validation intentionally happens before the key path is opened.
    review = validate_review(load_json(review_path, "blind review"))
    manifest_sha256 = sha256_file(manifest_path)
    if review["blind_manifest_sha256"] != manifest_sha256:
        raise ReviewError("review was completed against a different blind manifest")

    key_path = evaluation / "private" / "blind_key.json"
    expected_key_hash = manifest.get("private_key_sha256")
    actual_key_hash = sha256_file(key_path)
    if expected_key_hash != actual_key_hash:
        raise ReviewError("private key hash does not match the public blind manifest")
    assignment = validate_assignment(load_json(key_path, "private key"))
    rows = unblind_rows(review["planes"], assignment)

    blind_counts = {choice: 0 for choice in sorted(PREFERENCES)}
    arm_counts = {choice: 0 for choice in ("baseline", "manual", "tie", "unusable")}
    for row in rows:
        blind_counts[row["preference"]] += 1
        arm_counts[row["preferred_arm"]] += 1

    result = {
        "format": f"{FORMAT}-unblinded-review-v1",
        "claim_boundary": (
            "This records blinded visual preferences only. It does not select a winner or "
            "override the preregistered geometry/admission requirements."
        ),
        "blind_manifest_sha256": manifest_sha256,
        "review_sha256": sha256_file(review_path),
        "private_key_sha256": actual_key_hash,
        "assignment": assignment,
        "reviewer": review["reviewer"],
        "completed_utc": review["completed_utc"],
        "planes": rows,
        "preference_counts_by_blind_label": blind_counts,
        "preference_counts_by_arm": arm_counts,
        "global_notes": review.get("global_notes", ""),
    }
    output = args.out.resolve()
    if output.exists():
        raise ReviewError(f"refusing to overwrite unblinded result: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_json(result))
    print(f"wrote unblinded review: {output}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    subparsers = result.add_subparsers(dest="command", required=True)
    initialize_parser = subparsers.add_parser("init")
    initialize_parser.add_argument("--evaluation", type=Path, required=True)
    initialize_parser.add_argument("--review", type=Path, required=True)
    initialize_parser.set_defaults(func=initialize)
    unblind_parser = subparsers.add_parser("unblind")
    unblind_parser.add_argument("--evaluation", type=Path, required=True)
    unblind_parser.add_argument("--review", type=Path, required=True)
    unblind_parser.add_argument("--out", type=Path, required=True)
    unblind_parser.set_defaults(func=unblind)
    return result


def main() -> int:
    args = parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
