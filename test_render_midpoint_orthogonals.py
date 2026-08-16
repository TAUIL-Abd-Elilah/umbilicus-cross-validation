import unittest

import numpy as np
from PIL import Image

from render_midpoint_orthogonals import candidate_window, resize_isotropic


class OrthogonalGeometryTests(unittest.TestCase):
    def test_candidate_window_expands_to_include_entire_trajectory(self):
        trajectory = np.asarray([40.0, 75.0, 135.0])
        lo, hi, expanded = candidate_window(75.0, trajectory, radius=25, axis_size=200)
        self.assertTrue(expanded)
        self.assertLessEqual(lo, trajectory.min())
        self.assertGreaterEqual(hi - 1, trajectory.max())

    def test_candidate_window_fails_if_trajectory_leaves_volume(self):
        with self.assertRaisesRegex(ValueError, "leaves the source volume"):
            candidate_window(5.0, np.asarray([-1.0, 4.0]), radius=3, axis_size=20)

    def test_isotropic_resize_preserves_aspect_ratio(self):
        image = Image.new("L", (400, 200))
        resized = resize_isotropic(image, 620)
        self.assertEqual(resized.size, (620, 310))

    def test_isotropic_resize_rejects_invalid_target(self):
        with self.assertRaisesRegex(ValueError, "panel size must be positive"):
            resize_isotropic(Image.new("L", (2, 2)), 0)


if __name__ == "__main__":
    unittest.main()
