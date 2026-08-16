"""Render longitudinal (z-axis) sections of a scroll volume.

Rationale
---------
On a crushed scroll the umbilicus is not a local landmark in any single z-slice
(see PROTOCOL.md, Amendment 02): it is defined by how the windings connect along
the axis.  A section taken *along* z shows that structure directly — the windings
on either side of the core appear as two opposing stacks, and the umbilicus is the
seam between them, traced continuously over the whole scroll in a single image.

Reading a fixed-y (or fixed-x) plane cuts across the chunk layout instead of along
it, so the surgical range trick used for z-slices does not apply; these reads pull
whole chunks.  At level 4 that is ~80 MB for a full longitudinal plane, which is
acceptable because one plane replaces dozens of per-slice panels.
"""

from __future__ import annotations

import threading
import urllib.error
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from slicefetch import BUCKET, _get


class ChunkCache:
    """Whole-chunk fetcher with an in-memory LRU-ish store, shared across planes."""

    def __init__(
        self,
        pyramid,
        level: int,
        workers: int = 16,
        capacity: int = 512,
        *,
        strict: bool = False,
    ):
        self.pyr = pyramid
        self.level = level
        self.workers = workers
        self.capacity = capacity
        self.strict = strict
        self._store: dict[tuple[int, int, int], np.ndarray] = {}
        self._order: list[tuple[int, int, int]] = []
        self._lock = threading.Lock()
        self.bytes_fetched = 0
        self._missing_chunk_keys: set[tuple[int, int, int]] = set()
        self._failed_chunk_keys: set[tuple[int, int, int]] = set()

    @property
    def missing_chunks(self) -> int:
        return len(self._missing_chunk_keys)

    @property
    def failed_chunks(self) -> int:
        return len(self._failed_chunk_keys)

    def get(self, cz: int, cy: int, cx: int) -> np.ndarray:
        key = (cz, cy, cx)
        with self._lock:
            hit = self._store.get(key)
        if hit is not None:
            return hit
        czs, cys, cxs = self.pyr.chunks
        url = f"{BUCKET}/{self.pyr.path}/{self.level}/{cz}/{cy}/{cx}"
        fetched_bytes = 0
        try:
            raw = _get(url)
            arr = np.frombuffer(raw, dtype=np.uint8).reshape(czs, cys, cxs)
            fetched_bytes = len(raw)
        except urllib.error.HTTPError as error:
            if error.code == 404 and self.pyr.fill_values[self.level] == 0:
                arr = np.zeros((czs, cys, cxs), dtype=np.uint8)
                with self._lock:
                    self._missing_chunk_keys.add(key)
            elif self.strict:
                raise IOError(f"failed to fetch source chunk {url}") from error
            else:
                arr = np.zeros((czs, cys, cxs), dtype=np.uint8)
                with self._lock:
                    self._failed_chunk_keys.add(key)
        except Exception as error:
            if self.strict:
                raise IOError(f"failed to fetch source chunk {url}") from error
            arr = np.zeros((czs, cys, cxs), dtype=np.uint8)
            with self._lock:
                self._failed_chunk_keys.add(key)
        with self._lock:
            self.bytes_fetched += fetched_bytes
            self._store[key] = arr
            self._order.append(key)
            while len(self._order) > self.capacity:
                self._store.pop(self._order.pop(0), None)
        return arr

    def prefetch(self, keys) -> None:
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            list(pool.map(lambda k: self.get(*k), keys))


def plane_along_z(
    cache: ChunkCache,
    axis: str,
    fixed: int,
    z_range: tuple[int, int] | None = None,
    other_range: tuple[int, int] | None = None,
) -> np.ndarray:
    """Return a (z, other) plane at `level` coordinates.

    `axis='y'` fixes y and varies x; `axis='x'` fixes x and varies y.
    All coordinates are in *level* pixels, not full-resolution voxels.
    """
    sz, sy, sx = cache.pyr.shapes[cache.level]
    czs, cys, cxs = cache.pyr.chunks
    if axis == "y":
        n_other, fixed_size = sx, sy
    elif axis == "x":
        n_other, fixed_size = sy, sx
    else:
        raise ValueError("axis must be 'y' or 'x'")
    if not (0 <= fixed < fixed_size):
        raise IndexError(f"{axis}={fixed} out of range (size {fixed_size})")

    z0, z1 = z_range or (0, sz)
    o0, o1 = other_range or (0, n_other)
    out = np.zeros((z1 - z0, o1 - o0), dtype=np.uint8)

    cf = fixed // (cys if axis == "y" else cxs)
    lf = fixed % (cys if axis == "y" else cxs)

    keys = []
    for cz in range(z0 // czs, (z1 - 1) // czs + 1):
        for co in range(o0 // (cxs if axis == "y" else cys), (o1 - 1) // (cxs if axis == "y" else cys) + 1):
            keys.append((cz, cf, co) if axis == "y" else (cz, co, cf))
    cache.prefetch(keys)

    for key in keys:
        cz = key[0]
        co = key[2] if axis == "y" else key[1]
        arr = cache.get(*key)
        tile = arr[:, lf, :] if axis == "y" else arr[:, :, lf]
        gz0 = cz * czs
        go0 = co * (cxs if axis == "y" else cys)
        iz0, iz1 = max(z0, gz0), min(z1, gz0 + czs, sz)
        io0, io1 = max(o0, go0), min(o1, go0 + tile.shape[1], n_other)
        if iz1 <= iz0 or io1 <= io0:
            continue
        out[iz0 - z0 : iz1 - z0, io0 - o0 : io1 - o0] = tile[
            iz0 - gz0 : iz1 - gz0, io0 - go0 : io1 - go0
        ]
    return out


def curved_plane_along_z(
    cache: ChunkCache,
    axis: str,
    fixed_of_z,
    z_lo: int,
    z_hi: int,
    other_lo: int,
    other_hi: int,
) -> np.ndarray:
    """A longitudinal section that *follows a curve* instead of a constant plane.

    `fixed_of_z(z_level) -> fixed_level` gives, for each z, the coordinate of the
    axis being held.  This is what makes the z-continuity of the umbilicus usable
    without an interactive viewer: hold an approximate y(z) and the section shows
    the whole of x(z) at once, then hold that x(z) and read y(z) back.

    All coordinates are level pixels.
    """
    czs, cys, cxs = cache.pyr.chunks
    sz, sy, sx = cache.pyr.shapes[cache.level]
    out = np.zeros((z_hi - z_lo, other_hi - other_lo), dtype=np.uint8)

    fixed_size = sy if axis == "y" else sx
    other_chunk = cxs if axis == "y" else cys

    # group z by chunk so each (cz, cfixed, cother) is fetched once
    need: dict[tuple[int, int, int], None] = {}
    per_z = {}
    for z in range(z_lo, z_hi):
        f = int(round(fixed_of_z(z)))
        f = max(0, min(fixed_size - 1, f))
        per_z[z] = f
        cz, cf = z // czs, f // (cys if axis == "y" else cxs)
        for co in range(other_lo // other_chunk, (other_hi - 1) // other_chunk + 1):
            need[(cz, cf, co) if axis == "y" else (cz, co, cf)] = None
    cache.prefetch(list(need))

    for z in range(z_lo, z_hi):
        f = per_z[z]
        cz, lz = divmod(z, czs)
        cf, lf = divmod(f, cys if axis == "y" else cxs)
        for co in range(other_lo // other_chunk, (other_hi - 1) // other_chunk + 1):
            key = (cz, cf, co) if axis == "y" else (cz, co, cf)
            arr = cache.get(*key)
            row = arr[lz, lf, :] if axis == "y" else arr[lz, :, lf]
            go0 = co * other_chunk
            io0, io1 = max(other_lo, go0), min(other_hi, go0 + row.size)
            if io1 <= io0:
                continue
            out[z - z_lo, io0 - other_lo : io1 - other_lo] = row[io0 - go0 : io1 - go0]
    return out
