from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from PIL import Image

import approve_manual_curve as approval


SCROLL = "PHerc1203"


def points(offset: int = 0, count: int = 24):
    z_min = 1000
    z_max = 18900
    return [
        {
            "x": 3000 + offset + i,
            "y": 2500 + i,
            "z": round(z_min + i * (z_max - z_min) / (count - 1)),
            "score": 100,
        }
        for i in range(count)
    ]


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


class ApproveManualCurveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "approve_manual_curve.py").write_text("test tool\n", encoding="utf-8")
        self.seed = self.root / "seeds" / f"{SCROLL}_umbilicus_seed.json"
        self.estimate = self.root / "seeds" / f"{SCROLL}_umbilicus_estimated.json"
        write_json(self.seed, {"control_points": points(0)})
        write_json(self.estimate, {"control_points": points(100)})
        self.candidate = (
            self.root / "manual" / "candidates" / f"{SCROLL}_umbilicus.candidate.json"
        )
        write_json(self.candidate, {"control_points": points(20)})
        self.screenshots = []
        for position, z_value, color in (
            ("start", 1000, (20, 30, 40)),
            ("middle", 10000, (30, 40, 50)),
            ("end", 18900, (40, 50, 60)),
        ):
            path = (
                self.root
                / "manual"
                / "screenshots"
                / SCROLL
                / f"{SCROLL}_{position}_z{z_value}.png"
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (320, 256), color=color).save(path)
            self.screenshots.append(path)

    def tearDown(self):
        self.temp.cleanup()

    def approve(self, **overrides):
        arguments = {
            "root": self.root,
            "scroll": SCROLL,
            "candidate": self.candidate,
            "reviewer": "Human Reviewer",
            "qc_time": "2026-08-12T20:00:00+00:00",
            "ct_url": approval.expected_ct_url(SCROLL),
            "data_license": "CC-BY-4.0",
            "screenshots": self.screenshots,
            "qc_checked": True,
        }
        arguments.update(overrides)
        return approval.approve(**arguments)

    def test_approves_candidate_and_writes_hash_bound_manifest(self):
        candidate_bytes = self.candidate.read_bytes()
        final_path, manifest_path = self.approve()

        self.assertEqual(final_path.read_bytes(), candidate_bytes)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["format"], "villa-manual-umbilicus-qc-v2")
        self.assertTrue(manifest["qc_checked"])
        self.assertEqual(manifest["approved_curve"]["control_count"], 24)
        self.assertEqual(manifest["approved_curve"]["volume_shape_zyx"], [18977, 6844, 6844])
        self.assertEqual(
            {row["role"] for row in manifest["screenshots"]},
            {"start", "middle", "end"},
        )
        self.assertEqual(
            manifest["approved_curve"]["sha256"], approval.sha256_bytes(candidate_bytes)
        )
        self.assertEqual(len(manifest["screenshots"]), 3)
        self.assertTrue(
            all(not row["exact_coordinate_match"] for row in manifest["automatic_initializers"])
        )

    def test_rejects_untouched_automatic_curve(self):
        value = {"control_points": points(0)}
        write_json(self.candidate, value)
        with self.assertRaisesRegex(approval.ApprovalError, "untouched automatic seed"):
            self.approve()

    def test_rejects_candidate_outside_exact_working_path(self):
        other = self.root / "manual" / "wrong.json"
        write_json(other, {"control_points": points(20)})
        with self.assertRaisesRegex(approval.ApprovalError, "exact path"):
            self.approve(candidate=other)

    def test_rejects_bad_schema_count_duplicate_z_and_range(self):
        unordered = points(20)
        unordered[5], unordered[6] = unordered[6], unordered[5]
        cases = [
            ({"control_points": points(20, count=23)}, "24-40"),
            ({"control_points": unordered}, "ordered by increasing z"),
            (
                {"control_points": points(20)[:-1] + [{**points(20)[-1], "z": points(20)[-2]["z"]}]},
                "unique",
            ),
            (
                {"control_points": [{**point, "z": point["z"] + 30000} for point in points(20)]},
                "z range",
            ),
            (
                {"control_points": [{**point, "z": 8000 + index} for index, point in enumerate(points(20))]},
                "central 80%",
            ),
            (
                {"control_points": [{**point, "x": float(point["x"])} for point in points(20)]},
                "must be an integer",
            ),
            (
                {"control_points": [{**point, "x": 7000} for point in points(20)]},
                "outside volume bounds",
            ),
            (
                {"control_points": [{**point, "y": -1} for point in points(20)]},
                "outside volume bounds",
            ),
        ]
        for value, message in cases:
            with self.subTest(message=message):
                write_json(self.candidate, value)
                with self.assertRaisesRegex(approval.ApprovalError, message):
                    self.approve()

    def test_rejects_missing_qc_wrong_stream_license_or_screenshots(self):
        cases = [
            ({"qc_checked": False}, "qc-checked"),
            ({"reviewer": " "}, "reviewer"),
            ({"qc_time": "2026-08-12T20:00:00"}, "timezone"),
            ({"qc_time": "2030-08-12T20:00:00+00:00"}, "future"),
            ({"ct_url": "https://example.invalid/wrong.zarr"}, "CT URL mismatch"),
            ({"data_license": "UNKNOWN"}, "data-license"),
            ({"screenshots": self.screenshots[:2]}, "at least three"),
        ]
        for overrides, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(approval.ApprovalError, message):
                    self.approve(**overrides)

    def test_rejects_fake_image_and_missing_required_role(self):
        fake = self.screenshots[0]
        fake.write_bytes(b"not a decoded image")
        with self.assertRaisesRegex(approval.ApprovalError, "decodable image"):
            self.approve()

        Image.new("RGB", (320, 256)).save(fake)
        renamed = self.root / "manual" / "screenshots" / SCROLL / f"{SCROLL}_other_z18900.png"
        self.screenshots[-1].rename(renamed)
        with self.assertRaisesRegex(approval.ApprovalError, "missing: end"):
            self.approve(screenshots=[self.screenshots[0], self.screenshots[1], renamed])

    def test_rejects_missing_z_unordered_or_duplicate_required_evidence(self):
        end_without_z = (
            self.root / "manual" / "screenshots" / SCROLL / f"{SCROLL}_end.png"
        )
        self.screenshots[-1].rename(end_without_z)
        with self.assertRaisesRegex(approval.ApprovalError, "z<integer>"):
            self.approve(screenshots=[*self.screenshots[:2], end_without_z])
        end_without_z.rename(self.screenshots[-1])

        unordered_middle = (
            self.root / "manual" / "screenshots" / SCROLL / f"{SCROLL}_middle_z18950.png"
        )
        self.screenshots[1].rename(unordered_middle)
        with self.assertRaisesRegex(approval.ApprovalError, "strictly increasing"):
            self.approve(screenshots=[self.screenshots[0], unordered_middle, self.screenshots[2]])
        unordered_middle.rename(self.screenshots[1])

        shutil.copyfile(self.screenshots[0], self.screenshots[2])
        with self.assertRaisesRegex(approval.ApprovalError, "three distinct images"):
            self.approve()

    def test_refuses_overwrite(self):
        self.approve()
        with self.assertRaisesRegex(approval.ApprovalError, "refusing to overwrite"):
            self.approve()

    def test_protected_or_unknown_scroll_is_not_eligible(self):
        with self.assertRaisesRegex(approval.ApprovalError, "eligible-ten"):
            self.approve(scroll="PHerc0826")


if __name__ == "__main__":
    unittest.main()
