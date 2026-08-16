import unittest
import urllib.error
from unittest.mock import patch

import numpy as np

from longitudinal import ChunkCache


class FakePyramid:
    path = "fake"
    chunks = (2, 2, 2)
    fill_values = {0: 0}


class ChunkCacheTests(unittest.TestCase):
    @patch("longitudinal._get", side_effect=RuntimeError("network failed"))
    def test_strict_cache_fails_closed(self, _get):
        cache = ChunkCache(FakePyramid(), level=0, strict=True)
        with self.assertRaisesRegex(IOError, "failed to fetch source chunk"):
            cache.get(0, 0, 0)

    @patch("longitudinal._get", side_effect=RuntimeError("network failed"))
    def test_legacy_cache_can_still_fill_missing_chunk(self, _get):
        cache = ChunkCache(FakePyramid(), level=0)
        np.testing.assert_array_equal(cache.get(0, 0, 0), np.zeros((2, 2, 2), dtype=np.uint8))

    @patch(
        "longitudinal._get",
        side_effect=urllib.error.HTTPError("https://example.test/chunk", 404, "missing", {}, None),
    )
    def test_strict_cache_accepts_valid_zarr_fill_chunk_and_records_it(self, _get):
        cache = ChunkCache(FakePyramid(), level=0, strict=True)
        np.testing.assert_array_equal(cache.get(0, 0, 0), np.zeros((2, 2, 2), dtype=np.uint8))
        self.assertEqual(cache.missing_chunks, 1)
        self.assertEqual(cache.failed_chunks, 0)
        self.assertEqual(cache.bytes_fetched, 0)


if __name__ == "__main__":
    unittest.main()
