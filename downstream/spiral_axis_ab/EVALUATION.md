# PHerc1218 axis A/B evaluation

This evaluator is intentionally narrower than a general surface-quality suite.
It answers whether changing only the umbilicus produces a visibly or
geometrically different production Spiral fit without recycling optimizer
inputs as ground truth.

## Frozen visual evidence

The axial CT planes were fixed before either production result was inspected:

`5264, 5408, 5536, 5664, 5792, 5872, 5952`

They cover the window uniformly, include patch-boundary/interior locations,
and include the two largest pre-run axis disagreements. Both candidates are
drawn on byte-identical pixels from the PHerc1218
`20250521120456-8.640um-1.2m-116keV-masked.zarr` CT. Crop, contrast, colour,
line width, scale, and image size are identical. The A/B key is written outside
the shareable `blind/` directory. Both arms are restricted to their common
winding-ID range. The default render uses the exact scan's level-1 pyramid
(17.28 µm pixels) while retaining the frozen level-0 z coordinates. Crops are
expanded to exact pyramid-pixel boundaries and rendered at near-native
resolution with pixel-centre-correct coordinates. The blind
mapping is generated from a cryptographically random seed unless a fixed seed
is explicitly supplied for testing.

For every plane, a reviewer records `A`, `B`, `tie`, or `unusable`, a confidence
level, and a short reason before opening the key. The overlays are independent
scan evidence, but a visual vote is not an automatic ground-truth metric.

## Quantitative evidence boundaries

- `spiralcheck` intrinsic reports are label-free checks for crossings,
  collapsed/inflated gaps, and validity. Since radial ordering depends on an
  axis, both candidate axes are used as evaluation frames; a directional claim
  is robust only when it does not flip between frames. These metrics find
  defects, not anatomical truth.
- Villa patch/PCL satisfaction is summarized separately under
  `circular_constraint_diagnostics`. Those constraints were seen during
  fitting, so their scores only show whether the optimizer honored its inputs.
- The run-health admission gate requires relative PCL satisfaction >=94%,
  same-winding satisfaction >=91%, exactly three intersecting patches, and
  median radial pitch at CT level 1 in [9.6, 10.6] voxels at z=5420, 5620,
  and 5820. It is deliberately labelled circular/run-health, not quality.
- No winner is selected by the script.

## Run

```powershell
python evaluate_axis_ab.py `
  --baseline-run <baseline-fit-output> `
  --manual-run <manual-fit-output> `
  --baseline-umbilicus <public-pack-umbilicus.json> `
  --manual-umbilicus <manual-umbilicus.json> `
  --out <evaluation-output>
```

The script reuses the public MIT-licensed `Nicodol/spiralcheck` intrinsic
implementation and the public `sheetcheck` lazy CT reader, recording both Git
commits in `analysis/report.json`. The evaluator refuses revisions other than
`spiralcheck@d1b50e2` and `sheetcheck@7d53893`, refuses dirty dependency
worktrees, fingerprints every fitted-mesh byte, and will not overwrite a
non-empty evaluation package.
