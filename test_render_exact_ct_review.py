import unittest

import numpy as np
from PIL import Image

from render_exact_ct_review import compose_grid, point_at


class ExactCtReviewHelpersTests(unittest.TestCase):
    def test_point_at_interpolates_xy_at_z(self):
        points = np.asarray([[0.0, 10.0, 0.0], [20.0, 30.0, 10.0]])
        np.testing.assert_allclose(point_at(points, 5), [10.0, 20.0, 5.0])

    def test_point_at_rejects_extrapolation(self):
        points = np.asarray([[0.0, 10.0, 0.0], [20.0, 30.0, 10.0]])
        with self.assertRaisesRegex(ValueError, "outside curve range"):
            point_at(points, 11)

    def test_compose_grid_keeps_all_panels(self):
        first = Image.new("RGB", (10, 20), "red")
        second = Image.new("RGB", (30, 15), "blue")
        third = Image.new("RGB", (12, 8), "green")
        result = compose_grid([[first, second], [third]], gap=2)
        self.assertEqual(result.size, (42, 30))


if __name__ == "__main__":
    unittest.main()
