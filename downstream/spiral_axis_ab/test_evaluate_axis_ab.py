from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from evaluate_axis_ab import (
    admission_gate_from_metrics,
    aggregate_satisfaction,
    align_crop_to_level,
    blind_assignment,
    image_extent_l0,
    plane_segments,
    tree_fingerprint,
)


@dataclass
class FakeSurface:
    zyxs: np.ndarray

    @property
    def valid_vertex_mask(self):
        return np.all(self.zyxs != -1, axis=-1)

    @property
    def valid_quad_mask(self):
        valid = self.valid_vertex_mask
        return valid[:-1, :-1] & valid[1:, :-1] & valid[:-1, 1:] & valid[1:, 1:]

    @property
    def valid_zyxs(self):
        return self.zyxs[self.valid_vertex_mask]


class EvaluateAxisABTests(unittest.TestCase):
    def test_plane_segments_crosses_simple_quad(self):
        surface = FakeSurface(
            np.asarray(
                [
                    [[0.0, 10.0, 20.0], [0.0, 10.0, 30.0]],
                    [[2.0, 20.0, 20.0], [2.0, 20.0, 30.0]],
                ],
                dtype=np.float32,
            )
        )
        segments, ambiguous = plane_segments({0: surface}, 1.0)
        self.assertEqual(segments.shape, (1, 2, 2))
        self.assertEqual(ambiguous, 0)
        np.testing.assert_allclose(np.sort(segments[0, :, 0]), [20.0, 30.0])
        np.testing.assert_allclose(segments[0, :, 1], [15.0, 15.0])

    def test_invalid_quad_emits_no_segment(self):
        grid = np.asarray(
            [
                [[0.0, 0.0, 0.0], [-1.0, -1.0, -1.0]],
                [[2.0, 1.0, 0.0], [2.0, 1.0, 1.0]],
            ],
            dtype=np.float32,
        )
        segments, _ = plane_segments({0: FakeSurface(grid)}, 1.0)
        self.assertEqual(len(segments), 0)

    def test_blind_assignment_is_stable_and_complete(self):
        first = blind_assignment(123)
        self.assertEqual(first, blind_assignment(123))
        self.assertEqual(set(first), {"A", "B"})
        self.assertEqual(set(first.values()), {"baseline", "manual"})

    def test_ct_crop_alignment_preserves_pyramid_pixel_centres(self):
        crop = align_crop_to_level(
            (719, 7244, -2, 6787), scale=4, shape_yx=(2000, 1700)
        )
        self.assertEqual(crop, (716, 7244, 0, 6788))
        self.assertEqual(image_extent_l0(crop, 4), (-2.0, 6786.0, 7242.0, 714.0))

    def test_tree_fingerprint_binds_paths_and_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "a.bin").write_bytes(b"first")
            first = tree_fingerprint(root)
            self.assertEqual(first["file_count"], 1)
            self.assertEqual(first["total_bytes"], 5)
            (root / "b.bin").write_bytes(b"second")
            second = tree_fingerprint(root)
            self.assertNotEqual(first["tree_sha256"], second["tree_sha256"])

    def test_satisfaction_is_aggregated_and_marked_circular(self):
        value = {
            "patches": [
                {"satisfied_area": 3, "total_area": 4},
                {"satisfied_area": 1, "total_area": 2},
            ],
            "pcls": [
                {
                    "source_file": "relative_windings.json",
                    "satisfied_points": 1,
                    "total_points": 2,
                },
                {
                    "source_file": "relative_windings.json",
                    "satisfied_points": 2,
                    "total_points": 2,
                },
            ],
            "unverified_patches": [],
        }
        result = aggregate_satisfaction(value)
        self.assertIn("CIRCULAR", result["interpretation"])
        self.assertAlmostEqual(result["patches"]["weighted_fraction"], 4 / 6)
        group = result["pcls_by_source_file"]["relative_windings.json"]
        self.assertEqual(group["collections"], 2)
        self.assertAlmostEqual(group["fraction"], 3 / 4)

    def test_admission_gate_passes_only_all_preregistered_checks(self):
        gaps = [
            {"median_radial_gap_l1": value, "z_l0": z}
            for value, z in zip((9.9, 10.0, 10.2), (5420, 5620, 5820), strict=True)
        ]
        passed = admission_gate_from_metrics(
            relative_fraction=0.94,
            same_fraction=0.91,
            patch_count=3,
            radial_gap_records=gaps,
        )
        self.assertTrue(passed["passed"])
        self.assertIn("RUN-HEALTH", passed["interpretation"])

        failed = admission_gate_from_metrics(
            relative_fraction=0.939,
            same_fraction=0.91,
            patch_count=3,
            radial_gap_records=gaps,
        )
        self.assertFalse(failed["passed"])
        self.assertFalse(failed["checks"]["relative_points_at_least_94pct"])


if __name__ == "__main__":
    unittest.main()
