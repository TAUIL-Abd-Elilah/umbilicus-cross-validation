"""Surgical z-slice reader for the public Vesuvius OME-Zarr scroll volumes.

The scroll volumes are stored uncompressed (`compressor: null`, `dtype: |u1`) with
128x128x128 C-order chunks.  That makes a single z-slice of a single chunk one
contiguous 16 KiB run inside the chunk object, so an HTTP Range request can pull
exactly the bytes for one slice instead of the 2 MiB chunk.  Reading an 85-point
umbilicus at level 2 therefore costs tens of megabytes per scroll rather than
gigabytes, which keeps the whole job on the network and CPU while the GPU stays
free for other work.

Nothing here is scroll-specific; the only inputs are a bucket path and a level.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import numpy as np

BUCKET = "https://vesuvius-challenge-open-data.s3.amazonaws.com"


def _get(url: str, byte_range: tuple[int, int] | None = None, attempts: int = 5) -> bytes:
    """GET with backoff.  This bucket drops connections routinely under fan-out."""
    delay = 0.5
    for i in range(attempts):
        try:
            req = urllib.request.Request(url)
            if byte_range is not None:
                req.add_header("Range", f"bytes={byte_range[0]}-{byte_range[1]}")
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            if i == attempts - 1:
                raise
        except Exception:
            if i == attempts - 1:
                raise
        time.sleep(delay)
        delay = min(delay * 2, 8.0)
    raise RuntimeError("unreachable")


@dataclass(frozen=True)
class Pyramid:
    """One multiscale volume: the per-level shapes and the chunk geometry."""

    path: str
    shapes: dict[int, tuple[int, int, int]]
    chunks: tuple[int, int, int]
    fill_values: dict[int, int]

    @property
    def max_level(self) -> int:
        return max(self.shapes)

    def scale(self, level: int) -> int:
        """Full-resolution voxels per level-`level` voxel (assumes powers of two)."""
        return round(self.shapes[0][0] / self.shapes[level][0])


def open_pyramid(path: str, max_probe: int = 8) -> Pyramid:
    """Read the .zarray of every present pyramid level of `path`."""
    shapes: dict[int, tuple[int, int, int]] = {}
    fill_values: dict[int, int] = {}
    chunks: tuple[int, int, int] | None = None
    for lv in range(max_probe):
        try:
            meta = json.loads(_get(f"{BUCKET}/{path}/{lv}/.zarray", attempts=2))
        except urllib.error.HTTPError as error:
            if error.code == 404:
                break
            raise
        if meta.get("compressor") is not None or meta.get("dtype") != "|u1":
            raise ValueError(
                f"{path}/{lv}: reader assumes uncompressed uint8, got "
                f"dtype={meta.get('dtype')} compressor={meta.get('compressor')}"
            )
        if meta.get("order") != "C":
            raise ValueError(f"{path}/{lv}: reader assumes C order, got {meta.get('order')}")
        if meta.get("fill_value") != 0:
            raise ValueError(
                f"{path}/{lv}: missing chunks can only be zero-filled safely, got "
                f"fill_value={meta.get('fill_value')}"
            )
        shape = tuple(int(value) for value in meta["shape"])
        level_chunks = tuple(int(value) for value in meta["chunks"])
        if len(shape) != 3 or len(level_chunks) != 3:
            raise ValueError(f"{path}/{lv}: reader requires three-dimensional chunks")
        if any(value <= 0 for value in shape + level_chunks):
            raise ValueError(f"{path}/{lv}: shape and chunks must be positive")
        if chunks is not None and level_chunks != chunks:
            raise ValueError(
                f"{path}/{lv}: reader requires consistent chunk geometry, got "
                f"{level_chunks} after {chunks}"
            )
        shapes[lv] = shape
        fill_values[lv] = int(meta["fill_value"])
        chunks = level_chunks
    if not shapes or chunks is None:
        raise FileNotFoundError(f"no pyramid levels found under {path}")
    return Pyramid(path=path, shapes=shapes, chunks=chunks, fill_values=fill_values)


class SliceReader:
    """Fetches axis-aligned (y, x) windows of single z-slices, with a disk cache."""

    def __init__(self, pyramid: Pyramid, cache_dir: str | None = None, workers: int = 16):
        self.pyr = pyramid
        self.cache_dir = cache_dir
        self.workers = workers
        self._lock = threading.Lock()
        self.bytes_fetched = 0
        self.requests = 0
        self._missing_chunk_keys: set[str] = set()
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

    @property
    def missing_chunks(self) -> int:
        return len(self._missing_chunk_keys)

    # -- one chunk's worth of one slice ------------------------------------
    def _chunk_slice(self, level: int, cz: int, cy: int, cx: int, lz: int) -> np.ndarray:
        """The (128, 128) y/x tile of local-z `lz` inside chunk (cz, cy, cx)."""
        czs, cys, cxs = self.pyr.chunks
        key = f"{self.pyr.path}/{level}/{cz}/{cy}/{cx}"
        start = lz * cys * cxs
        cached = None
        if self.cache_dir:
            safe = key.replace("/", "_")
            cached = os.path.join(self.cache_dir, f"{safe}_z{lz}.npy")
            if os.path.exists(cached):
                tile = np.load(cached, allow_pickle=False)
                if tile.shape != (cys, cxs) or tile.dtype != np.uint8:
                    raise IOError(
                        f"invalid cached tile {cached}: shape={tile.shape}, dtype={tile.dtype}"
                    )
                return tile
        try:
            raw = _get(f"{BUCKET}/{key}", byte_range=(start, start + cys * cxs - 1))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # Missing chunk: zarr semantics say it reads as fill_value.
                if self.pyr.fill_values[level] != 0:
                    raise IOError(
                        f"{key}: missing chunk requires unsupported fill_value "
                        f"{self.pyr.fill_values[level]}"
                    ) from e
                with self._lock:
                    self._missing_chunk_keys.add(key)
                return np.zeros((cys, cxs), dtype=np.uint8)
            raise
        with self._lock:
            self.bytes_fetched += len(raw)
            self.requests += 1
        if len(raw) != cys * cxs:
            raise IOError(f"{key}: expected {cys * cxs} bytes for z-slice, got {len(raw)}")
        tile = np.frombuffer(raw, dtype=np.uint8).reshape(cys, cxs)
        if cached:
            np.save(cached, tile)
        return tile

    # -- public API ---------------------------------------------------------
    def read_window(
        self, level: int, z: int, y0: int, y1: int, x0: int, x1: int
    ) -> np.ndarray:
        """Return volume[z, y0:y1, x0:x1] at `level`, clipped to the volume bounds.

        Out-of-bounds requests are zero-padded so callers can centre a fixed-size
        window on a point near the volume edge without special-casing.
        """
        sz, sy, sx = self.pyr.shapes[level]
        czs, cys, cxs = self.pyr.chunks
        if not (0 <= z < sz):
            raise IndexError(f"z={z} out of range for level {level} (size {sz})")
        out = np.zeros((y1 - y0, x1 - x0), dtype=np.uint8)

        cz, lz = divmod(z, czs)
        cy_lo, cy_hi = max(0, y0) // cys, (min(sy, y1) - 1) // cys
        cx_lo, cx_hi = max(0, x0) // cxs, (min(sx, x1) - 1) // cxs
        if min(sy, y1) <= max(0, y0) or min(sx, x1) <= max(0, x0):
            return out

        jobs = [
            (cy, cx)
            for cy in range(cy_lo, cy_hi + 1)
            for cx in range(cx_lo, cx_hi + 1)
        ]

        def one(job):
            cy, cx = job
            return job, self._chunk_slice(level, cz, cy, cx, lz)

        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            for (cy, cx), tile in pool.map(one, jobs):
                gy0, gx0 = cy * cys, cx * cxs
                # intersection of this chunk with the requested window
                iy0, iy1 = max(y0, gy0), min(y1, gy0 + cys, sy)
                ix0, ix1 = max(x0, gx0), min(x1, gx0 + cxs, sx)
                if iy1 <= iy0 or ix1 <= ix0:
                    continue
                out[iy0 - y0 : iy1 - y0, ix0 - x0 : ix1 - x0] = tile[
                    iy0 - gy0 : iy1 - gy0, ix0 - gx0 : ix1 - gx0
                ]
        return out

    def read_full_slice(self, level: int, z: int) -> np.ndarray:
        """The whole (y, x) plane at `level`, `z`.  Only sane at coarse levels."""
        _, sy, sx = self.pyr.shapes[level]
        return self.read_window(level, z, 0, sy, 0, sx)


def scroll_volume_path(scroll: str, ct_volume: str) -> str:
    return f"{scroll}/volumes/{ct_volume}"
