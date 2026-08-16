import json
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

import numpy as np

from slicefetch import Pyramid, SliceReader, open_pyramid


def metadata(fill_value=0, chunks=(2, 2, 2)):
    return json.dumps(
        {
            "shape": [4, 4, 4],
            "chunks": list(chunks),
            "dtype": "|u1",
            "compressor": None,
            "order": "C",
            "fill_value": fill_value,
        }
    ).encode()


class SliceFetchTests(unittest.TestCase):
    @patch("slicefetch._get")
    def test_open_pyramid_records_validated_fill_value(self, get):
        def response(url, *args, **kwargs):
            if "/0/.zarray" in url:
                return metadata(0)
            raise urllib.error.HTTPError(url, 404, "missing", {}, None)

        get.side_effect = response
        pyramid = open_pyramid("scroll/volume", max_probe=2)
        self.assertEqual(pyramid.fill_values, {0: 0})

    @patch("slicefetch._get", return_value=metadata(7))
    def test_open_pyramid_rejects_nonzero_missing_chunk_semantics(self, get):
        with self.assertRaisesRegex(ValueError, "fill_value=7"):
            open_pyramid("scroll/volume", max_probe=1)

    @patch("slicefetch._get", side_effect=OSError("network failure"))
    def test_open_pyramid_does_not_hide_non_404_metadata_failure(self, get):
        with self.assertRaisesRegex(OSError, "network failure"):
            open_pyramid("scroll/volume", max_probe=1)

    @patch("slicefetch._get")
    def test_open_pyramid_rejects_mixed_chunk_geometry(self, get):
        get.side_effect = [metadata(chunks=(2, 2, 2)), metadata(chunks=(1, 2, 2))]
        with self.assertRaisesRegex(ValueError, "consistent chunk geometry"):
            open_pyramid("scroll/volume", max_probe=2)

    @patch(
        "slicefetch._get",
        side_effect=urllib.error.HTTPError("https://example.test/chunk", 404, "missing", {}, None),
    )
    def test_slice_reader_records_valid_zarr_fill_chunk(self, get):
        pyramid = Pyramid(
            path="scroll/volume",
            shapes={0: (2, 2, 2)},
            chunks=(2, 2, 2),
            fill_values={0: 0},
        )
        reader = SliceReader(pyramid)
        np.testing.assert_array_equal(reader._chunk_slice(0, 0, 0, 0, 0), np.zeros((2, 2), dtype=np.uint8))
        self.assertEqual(reader.missing_chunks, 1)

    def test_slice_reader_rejects_corrupt_cache_tile(self):
        pyramid = Pyramid(
            path="scroll/volume",
            shapes={0: (2, 2, 2)},
            chunks=(2, 2, 2),
            fill_values={0: 0},
        )
        with tempfile.TemporaryDirectory() as directory:
            reader = SliceReader(pyramid, cache_dir=directory)
            safe = "scroll_volume_0_0_0_0_z0.npy"
            np.save(Path(directory) / safe, np.zeros((1, 1), dtype=np.uint8))
            with self.assertRaisesRegex(IOError, "invalid cached tile"):
                reader._chunk_slice(0, 0, 0, 0, 0)


if __name__ == "__main__":
    unittest.main()
