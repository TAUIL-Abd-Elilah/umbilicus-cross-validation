from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

import compare_independent_curves as comparison


def write_curve(path: Path, points: list[tuple[float, float, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {"control_points": [{"x": x, "y": y, "z": z} for x, y, z in points]}
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


class IndependentCurveComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.ours = self.root / "ours.json"
        self.reference = self.root / "reference.json"

    def tearDown(self):
        self.temp.cleanup()

    def test_same_z_interpolation_and_physical_metrics(self):
        write_curve(self.ours, [(0, 0, 0), (10, 0, 10)])
        write_curve(self.reference, [(2, 10, 2), (10, 10, 10)])
        metrics, rows = comparison.compare_one(
            "PHerc0191",
            self.ours,
            self.reference,
            candidate_count=1,
            candidate_separation_z=1,
        )
        self.assertEqual(metrics["shared_z_range"], [2, 10])
        self.assertEqual(metrics["sample_count"], 9)
        self.assertTrue(all(abs(row["distance_voxels"] - 10.0) < 1e-9 for row in rows))
        self.assertAlmostEqual(metrics["distance"]["median_mm"], 0.09362)
        self.assertEqual(metrics["ct_review_candidates"][0]["status"], "requires_exact_ct_review")

    def test_candidate_selection_is_separated_and_deterministic(self):
        z = np.arange(10)
        ours = np.column_stack((np.zeros(10), np.zeros(10)))
        reference = np.column_stack((np.array([0, 9, 8, 7, 0, 6, 5, 0, 4, 3]), np.zeros(10)))
        distances = np.linalg.norm(ours - reference, axis=1)
        candidates = comparison.review_candidates(z, ours, reference, distances, 10.0, 3, 3)
        self.assertEqual([row["z"] for row in candidates], [1, 5, 8])

    def test_disagreement_bands_are_contiguous_and_peak_sorted(self):
        z = np.arange(8)
        values = np.array([0.0, 2.0, 3.0, 0.0, 2.5, 2.4, 0.0, 4.0])
        bands = comparison.disagreement_bands(z, values, 2.0)
        self.assertEqual([band["peak_z"] for band in bands], [7, 2, 4])
        self.assertEqual(bands[1]["z_start"], 1)
        self.assertEqual(bands[1]["z_end"], 2)

    def test_rejects_bad_z_and_nonoverlap(self):
        write_curve(self.ours, [(0, 0, 0), (0, 0, 0)])
        with self.assertRaisesRegex(comparison.ComparisonError, "unique and increasing"):
            comparison.load_curve(self.ours)

        write_curve(self.ours, [(0, 0, 0), (0, 0, 1)])
        write_curve(self.reference, [(0, 0, 2), (0, 0, 3)])
        with self.assertRaisesRegex(comparison.ComparisonError, "no shared z"):
            comparison.compare_one("PHerc0191", self.ours, self.reference)

    def test_cli_single_curve_overrides_bind_actual_inputs(self):
        write_curve(self.ours, [(0, 0, 0), (10, 0, 10)])
        write_curve(self.reference, [(0, 1, 0), (10, 1, 10)])
        output = self.root / "result.json"
        code = comparison.main(
            [
                "--reference-dir",
                str(self.root),
                "--scroll",
                "PHerc0191",
                "--ours-path",
                str(self.ours),
                "--reference-path",
                str(self.reference),
                "--output",
                str(output),
            ]
        )
        self.assertEqual(code, 0)
        result = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result["scroll_count"], 1)
        self.assertEqual(result["scrolls"][0]["ours"]["sha256"], comparison.sha256(self.ours))
        self.assertEqual(
            result["scrolls"][0]["reference"]["sha256"],
            comparison.sha256(self.reference),
        )


if __name__ == "__main__":
    unittest.main()
