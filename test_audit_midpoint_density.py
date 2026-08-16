import unittest
from pathlib import Path

import numpy as np

from audit_midpoint_density import portable_path, segment_rows, selection_slug, select_segment_rows


class SegmentRowsTests(unittest.TestCase):
    def test_turn_risk_uses_xy_not_z(self):
        points = np.asarray(
            [
                [0.0, 0.0, 0.0],
                [10.0, 0.0, 1000.0],
                [10.0, 10.0, 2000.0],
                [20.0, 10.0, 3000.0],
            ]
        )
        rows = segment_rows(points, level_scale=4)
        self.assertAlmostEqual(rows[0]["right_turn_degrees"], 90.0)
        self.assertAlmostEqual(rows[1]["left_turn_degrees"], 90.0)
        self.assertAlmostEqual(rows[1]["right_turn_degrees"], 90.0)

    def test_midpoint_is_aligned_and_interpolated_at_exact_z(self):
        points = np.asarray([[0.0, 10.0, 1.0], [16.0, 26.0, 10.0]])
        row = segment_rows(points, level_scale=4)[0]
        self.assertEqual(row["exact_mid_xyz"], [5.333333333333333, 15.333333333333332, 4.0])

    def test_non_increasing_z_is_rejected(self):
        points = np.asarray([[0.0, 0.0, 5.0], [1.0, 1.0, 5.0]])
        with self.assertRaisesRegex(ValueError, "control z must increase"):
            segment_rows(points, level_scale=4)

    def test_segment_without_aligned_pyramid_slice_is_rejected(self):
        points = np.asarray([[0.0, 0.0, 1.0], [1.0, 1.0, 3.0]])
        with self.assertRaisesRegex(ValueError, "no pyramid-aligned slice"):
            segment_rows(points, level_scale=4)

    def test_segment_selection_is_one_based_sorted_and_validated(self):
        rows = [{"segment_index": index} for index in range(4)]
        self.assertEqual(
            select_segment_rows(rows, [4, 2, 2]),
            [{"segment_index": 1}, {"segment_index": 3}],
        )
        with self.assertRaisesRegex(ValueError, "outside 1..4"):
            select_segment_rows(rows, [0, 5])

    def test_manifest_paths_are_repository_relative(self):
        root = Path(__file__).resolve().parent
        self.assertEqual(
            portable_path(root / "manual" / "curve.json", root),
            "manual/curve.json",
        )

    def test_external_manifest_path_does_not_expose_local_parent(self):
        root = (Path.cwd() / "repository").resolve()
        external = root.parent / "private" / "curve.json"
        self.assertEqual(portable_path(external, root), "external-input/curve.json")

    def test_selection_slug_is_stable_and_one_based(self):
        rows = [{"segment_index": 0}, {"segment_index": 11}]
        self.assertEqual(selection_slug(rows), "001-012")


if __name__ == "__main__":
    unittest.main()
