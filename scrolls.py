"""The 13 Grand-Prize-eligible scrolls and their public CT volumes.

Volume names come from the open-data bucket listing; shapes are (z, y, x) at
full resolution.  `has_reference` marks the curves that already existed publicly
before this project and are therefore used for validation rather than produced.
"""

SCROLLS = {
    "PHerc0125": dict(ct="20250821151825-9.362um-1.2m-113keV-masked.zarr", shape=(20840, 8387, 8387), um=9.362),
    "PHerc0191": dict(ct="20250821151635-9.362um-1.2m-113keV-masked.zarr", shape=(18977, 8387, 8387), um=9.362),
    "PHerc0211": dict(ct="20250821151803-9.362um-1.2m-113keV-masked.zarr", shape=(19416, 7948, 7948), um=9.362),
    "PHerc0257": dict(ct="20250821151750-9.362um-1.2m-113keV-masked.zarr", shape=(18872, 8388, 8388), um=9.362),
    "PHerc0268": dict(ct="20251110183117-8.640um-1.2m-116keV-masked.zarr", shape=(14833, 12145, 12145), um=8.640),
    "PHerc0358": dict(ct="20250821151737-9.362um-1.2m-113keV-masked.zarr", shape=(14744, 7783, 7783), um=9.362),
    "PHerc0800": dict(ct="20250521135224-8.640um-1.2m-116keV-masked.zarr", shape=(24298, 9867, 9867), um=8.640),
    "PHerc0813": dict(ct="20250821151723-9.362um-1.2m-113keV-masked.zarr", shape=(16993, 7947, 7947), um=9.362),
    "PHerc0826": dict(ct="20250821151701-9.362um-1.2m-113keV-masked.zarr", shape=(16920, 8169, 8169), um=9.362),
    "PHerc1203": dict(ct="20250820131727-9.362um-1.2m-113keV-masked.zarr", shape=(18977, 6844, 6844), um=9.362),
    "PHerc1218": dict(ct="20250521120456-8.640um-1.2m-116keV-masked.zarr", shape=(23247, 7593, 7593), um=8.640),
    "PHerc1447": dict(ct="20250521151220-8.640um-1.2m-116keV-masked.zarr", shape=(24297, 8343, 8343), um=8.640),
    "PHerc1545": dict(ct="20250821151648-9.362um-1.2m-113keV-masked.zarr", shape=(20961, 7506, 7506), um=9.362),
}

# Public curves that predate this project.
REFERENCE = {
    "PHerc0125": "Sean Johnson (@Bruniss), khartes, 2026-08-08, posted in #general",
    "PHerc0211": "Sean Johnson (@Bruniss), khartes, 2026-08-08, posted in #general",
    "PHerc0826": "Sean Johnson (@Bruniss), khartes, 2026-08-08, posted in #general",
    "PHerc1218": "IyanDopico/vesuvius-sheet-tools (spiral_input_pherc1218/umbilicus.json)",
}

TO_PRODUCE = [s for s in SCROLLS if s not in ("PHerc0125", "PHerc0211", "PHerc0826")]
