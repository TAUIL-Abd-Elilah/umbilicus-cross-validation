"""Reader for the published lasagna normal-field predictions.

The lasagna model is trained to predict the sheet normal directly ("the vector
perpendicular to the sheet, plus the local winding density as 1/distance"), which
is a far cleaner estimate of sheet orientation than a structure tensor computed on
raw CT.  Both maintainers suggested it as the route to automating the umbilicus:

    Bruniss  — "Could prob automate w/ the lasagna normals?"
    waldkauz — "We could port it to lasagna normals, should be more robust."

Layout differs from the CT volumes: components are separate OME-Zarr stores
(`<scroll>_nx`, `_ny`, `_cos`, `_grad_mag`), blosc-compressed with 32^3 chunks, and
the multiscale levels start at path "2" (scale 4) rather than "0".  Values are uint8
and are mapped back to [-1, 1].
"""

from __future__ import annotations

import json
import re
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from slicefetch import BUCKET, _get

_LASAGNA_ROOT = "{scroll}/representations/predictions/lasagna/"


def find_lasagna_run(scroll: str) -> str:
    """Return the bucket prefix of the (single) lasagna run for `scroll`."""
    prefix = _LASAGNA_ROOT.format(scroll=scroll)
    url = f"{BUCKET}?list-type=2&delimiter=/&max-keys=1000&prefix={prefix}"
    body = _get(url).decode("utf-8", "replace")
    runs = [p for p in re.findall(r"<Prefix>([^<]+)</Prefix>", body) if p != prefix]
    if not runs:
        raise FileNotFoundError(f"no lasagna run under {prefix}")
    return sorted(runs)[-1]


class LasagnaComponent:
    """One component store (nx / ny / cos / grad_mag) at one pyramid level."""

    def __init__(self, scroll: str, run: str, component: str, level: int):
        self.path = f"{run}{scroll}_{component}.ome.zarr"
        self.level = level
        meta = json.loads(_get(f"{BUCKET}/{self.path}/{level}/.zarray"))
        self.shape = tuple(meta["shape"])
        self.chunks = tuple(meta["chunks"])
        self.dtype = np.dtype(meta["dtype"])
        self.compressor = meta.get("compressor")
        self.fill = meta.get("fill_value", 0)
        self._lock = threading.Lock()
        self._cache: dict[tuple[int, int, int], np.ndarray] = {}
        self.bytes_fetched = 0

    def _decode(self, raw: bytes) -> np.ndarray:
        cid = (self.compressor or {}).get("id")
        if cid == "blosc":
            import numcodecs

            buf = numcodecs.Blosc().decode(raw)
        elif cid is None:
            buf = raw
        else:
            import numcodecs

            buf = numcodecs.get_codec(self.compressor).decode(raw)
        return np.frombuffer(buf, dtype=self.dtype).reshape(self.chunks)

    def chunk(self, cz: int, cy: int, cx: int) -> np.ndarray:
        key = (cz, cy, cx)
        with self._lock:
            hit = self._cache.get(key)
        if hit is not None:
            return hit
        try:
            raw = _get(f"{BUCKET}/{self.path}/{self.level}/{cz}/{cy}/{cx}", attempts=3)
            arr = self._decode(raw)
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            arr = np.full(self.chunks, self.fill, dtype=self.dtype)
        except Exception:
            arr = np.full(self.chunks, self.fill, dtype=self.dtype)
        with self._lock:
            self.bytes_fetched += arr.size
            self._cache[key] = arr
        return arr

    def read_window(self, z: int, y0: int, y1: int, x0: int, x1: int, workers: int = 24) -> np.ndarray:
        sz, sy, sx = self.shape
        czs, cys, cxs = self.chunks
        out = np.full((y1 - y0, x1 - x0), self.fill, dtype=self.dtype)
        if not (0 <= z < sz):
            raise IndexError(f"z={z} out of range (size {sz})")
        cz, lz = divmod(z, czs)
        yl, yh = max(0, y0), min(sy, y1)
        xl, xh = max(0, x0), min(sx, x1)
        if yh <= yl or xh <= xl:
            return out
        jobs = [
            (cy, cx)
            for cy in range(yl // cys, (yh - 1) // cys + 1)
            for cx in range(xl // cxs, (xh - 1) // cxs + 1)
        ]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            fetched = list(pool.map(lambda j: (j, self.chunk(cz, j[0], j[1])), jobs))
        for (cy, cx), arr in fetched:
            tile = arr[lz]
            gy0, gx0 = cy * cys, cx * cxs
            iy0, iy1 = max(y0, gy0), min(y1, gy0 + cys, sy)
            ix0, ix1 = max(x0, gx0), min(x1, gx0 + cxs, sx)
            if iy1 <= iy0 or ix1 <= ix0:
                continue
            out[iy0 - y0 : iy1 - y0, ix0 - x0 : ix1 - x0] = tile[
                iy0 - gy0 : iy1 - gy0, ix0 - gx0 : ix1 - gx0
            ]
        return out


class LasagnaNormals:
    """The (ny, nx) sheet-normal field and its confidence, at one pyramid level."""

    def __init__(self, scroll: str, level: int = 4):
        run = find_lasagna_run(scroll)
        self.scroll = scroll
        self.level = level
        self.nx = LasagnaComponent(scroll, run, "nx", level)
        self.ny = LasagnaComponent(scroll, run, "ny", level)
        self.grad = LasagnaComponent(scroll, run, "grad_mag", level)
        self.shape = self.nx.shape
        # the store's own scale attribute; level "2" is scale 4 relative to full res
        self.scale = 2 ** level

    @property
    def bytes_fetched(self) -> int:
        return self.nx.bytes_fetched + self.ny.bytes_fetched + self.grad.bytes_fetched

    def read(self, z: int, y0: int, y1: int, x0: int, x1: int):
        """Return (normal_yx, weight) for a window, normals unit-length in-plane."""
        nx = self.nx.read_window(z, y0, y1, x0, x1).astype(np.float32)
        ny = self.ny.read_window(z, y0, y1, x0, x1).astype(np.float32)
        gm = self.grad.read_window(z, y0, y1, x0, x1).astype(np.float32)

        # uint8 encodes [-1, 1]
        vx = nx / 255.0 * 2.0 - 1.0
        vy = ny / 255.0 * 2.0 - 1.0
        mag = np.hypot(vy, vx)
        ok = mag > 1e-3
        vy = np.where(ok, vy / np.maximum(mag, 1e-6), 0.0)
        vx = np.where(ok, vx / np.maximum(mag, 1e-6), 0.0)

        # in-plane magnitude is itself a confidence: where the sheet normal points
        # mostly along z the in-plane projection is short and its direction is noise
        weight = np.where(ok, mag, 0.0) * (gm / 255.0)
        return np.stack([vy, vx], axis=-1), weight.astype(np.float32)
