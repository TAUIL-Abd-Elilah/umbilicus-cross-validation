from __future__ import annotations

import unittest

from evaluate_axis_ab import FORMAT, FROZEN_PLANES
from unblind_axis_ab import (
    REVIEW_FORMAT,
    ReviewError,
    make_template,
    unblind_rows,
    validate_assignment,
    validate_review,
)


class UnblindAxisABTests(unittest.TestCase):
    def valid_review(self):
        value = make_template(
            {"format": FORMAT, "frozen_planes_l0": list(FROZEN_PLANES)}, "a" * 64
        )
        value.update(
            {
                "reviewer": "blind reviewer",
                "completed_utc": "2026-08-16T22:00:00+00:00",
                "attestation": {
                    "identity_key_opened_before_completion": False,
                    "reviewed_only_blind_assets": True,
                },
            }
        )
        for row in value["planes"]:
            row.update(
                {
                    "preference": "A",
                    "confidence": "medium",
                    "reason": "Candidate A follows the visible sheet more continuously.",
                }
            )
        return value

    def test_template_is_invalid_until_completed(self):
        template = make_template(
            {"format": FORMAT, "frozen_planes_l0": list(FROZEN_PLANES)}, "a" * 64
        )
        self.assertEqual(template["format"], REVIEW_FORMAT)
        with self.assertRaises(ReviewError):
            validate_review(template)

    def test_complete_review_passes(self):
        self.assertEqual(validate_review(self.valid_review())["reviewer"], "blind reviewer")

    def test_missing_plane_or_opened_key_fails_closed(self):
        review = self.valid_review()
        review["planes"].pop()
        with self.assertRaises(ReviewError):
            validate_review(review)
        review = self.valid_review()
        review["attestation"]["identity_key_opened_before_completion"] = True
        with self.assertRaises(ReviewError):
            validate_review(review)

    def test_assignment_and_rows_unblind_without_selecting_winner(self):
        assignment = validate_assignment(
            {"format": FORMAT, "assignment": {"A": "manual", "B": "baseline"}}
        )
        rows = unblind_rows(self.valid_review()["planes"], assignment)
        self.assertEqual({row["preferred_arm"] for row in rows}, {"manual"})


if __name__ == "__main__":
    unittest.main()
