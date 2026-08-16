from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import run_axis_ab as experiment


def write_axis(path: Path, points: list[tuple[float, float, float]]) -> None:
    path.write_text(
        json.dumps(
            {
                "control_points": [
                    {"x": x, "y": y, "z": z} for x, y, z in points
                ]
            }
        ),
        encoding="utf-8",
    )


class AxisAbTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_axis_validation_and_disagreement(self) -> None:
        first = self.root / "a.json"
        second = self.root / "b.json"
        write_axis(first, [(0, 0, 5000), (10, 0, 6200)])
        write_axis(second, [(3, 4, 5000), (13, 4, 6200)])
        result = experiment.axis_disagreement(first, second)
        self.assertEqual(result["sample_count"], 800)
        self.assertAlmostEqual(result["minimum_voxels"], 5.0)
        self.assertAlmostEqual(result["median_voxels"], 5.0)
        self.assertAlmostEqual(result["maximum_voxels"], 5.0)

    def test_rejects_non_increasing_or_short_axis(self) -> None:
        path = self.root / "bad.json"
        write_axis(path, [(0, 0, 5000), (1, 1, 5000)])
        with self.assertRaisesRegex(experiment.ExperimentError, "strictly increase"):
            experiment.axis_points(path)
        write_axis(path, [(0, 0, 5300), (1, 1, 6100)])
        with self.assertRaisesRegex(experiment.ExperimentError, "does not cover"):
            experiment.axis_points(path)

    def test_config_freezes_production_treatment(self) -> None:
        config = experiment.fit_config(30000)
        self.assertEqual(config["z_begin"], 5220)
        self.assertEqual(config["z_end"], 6020)
        self.assertEqual(config["optimizer_random_seed"], 1)
        self.assertEqual(config["optimizer_num_training_steps"], 30000)
        self.assertEqual(config["sample_count_unattached_pcls_per_step"], 800)
        self.assertFalse(config["pcl_stratified_pcl_sampling"])
        self.assertEqual(config["dense_spacing_mode"], "grad_mag")
        self.assertEqual(config["loss_weight_min_spacing"], 0.0)
        self.assertEqual(config["loss_weight_dense_spacing_density"], 0.0)
        self.assertIsNone(config["shell_outer_winding_idx"])

    def test_manifest_omit_allows_only_axis_difference(self) -> None:
        first = self.root / "first"
        second = self.root / "second"
        first.mkdir()
        second.mkdir()
        (first / "same.txt").write_text("same", encoding="utf-8")
        (second / "same.txt").write_text("same", encoding="utf-8")
        (first / "umbilicus.json").write_text("first", encoding="utf-8")
        (second / "umbilicus.json").write_text("second", encoding="utf-8")
        self.assertEqual(
            experiment.file_manifest(first, omit=("umbilicus.json",)),
            experiment.file_manifest(second, omit=("umbilicus.json",)),
        )


if __name__ == "__main__":
    unittest.main()
