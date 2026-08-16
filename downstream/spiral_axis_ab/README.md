# PHerc1218 production Spiral axis A/B

This experiment asks one narrow, previously unanswered question: with the
production Spiral fitter, constraints, window, random seed, and optimization
held fixed, does changing only the PHerc1218 umbilicus materially change the
fitted surface?

It is deliberately not another umbilicus-comparison plot. The treatment is fed
through the real fitter and the resulting surfaces are reviewed on the volume.

## Pinned comparison

| Item | Pin |
|---|---|
| Villa fitter | `ScrollPrize/villa@465cab06084e5587f7aea989440d495318bfb1eb` (merged `main`, including PR #1461) |
| Constraint pack | `IyanDopico/vesuvius-sheet-tools@7116a75521e4f5791a4d077311efb5558bf3e20e` |
| Arm A | pack `umbilicus.json` |
| Arm B | `AlexeyDrobkovStrikesBack/herculaneum-umbilici@57e09a3d6f25773a2e0cad9d21eb97296cef50c8/PHerc1218_umbilicus.json` |
| Window | full-resolution `z=[5220,6020)` |
| Seed / steps | `1` / `30,000` |

The selected 800-slice window contains three published seed patches and passed
the public sweep (96.6% relative-winding, 93.3% same-winding, median radial
steps 9.99/10.01/10.27 L1 voxels). The two axes disagree by 467–572
full-resolution voxels here, so this is a sensitive, anchored test.

## Preregistered interpretation

The PCLs, seed patches, and Arm A axis all derive from the same stitched-label
source. Their satisfaction scores are therefore useful run-health checks but
are **not independent truth** and cannot by themselves establish that Arm A is
better.

The decision order is frozen before the fits:

1. Both arms must exit successfully, fit exactly three intersecting patches,
   use byte-identical non-axis inputs, and pass the public relative/same-winding
   and radial-spacing health bands.
2. Compare the actual fitted surfaces on identical CT planes and in an official
   flattening/render, with arm labels hidden during review. Surface continuity,
   fold crossings, doubled/missed layers, and geometric failures are the
   primary evidence.
3. Report a win only if the volume evidence and at least one independent
   geometry metric agree. Otherwise report the result as neutral or
   inconclusive. Never silently replace a public axis.

The machine-readable freeze is in [`preregistration.json`](preregistration.json).

## Reproduce

Use an isolated Python 3.14 CUDA environment with PyTorch 2.12.x. PyTorch
2.13+ is refused because a reported transform-inverse lifetime regression can
exhaust VRAM in this fitter.

```powershell
python downstream/spiral_axis_ab/run_axis_ab.py prepare `
  --work downstream/spiral_axis_ab/work `
  --villa-dir ..\_worktrees\villa-axis-ab-current `
  --pack-dir ..\_worktrees\sheet-tools-pack-7116a75\data\spiral_input_pherc1218 `
  --manual-repo ..\_external\herculaneum-umbilici

# Admission/IO smoke test; not scientific evidence.
python downstream/spiral_axis_ab/run_axis_ab.py run `
  --work downstream/spiral_axis_ab/work `
  --villa-dir ..\_worktrees\villa-axis-ab-current `
  --python C:\path\to\python.exe --phase smoke --steps 300

# Preregistered production pair.
python downstream/spiral_axis_ab/run_axis_ab.py run `
  --work downstream/spiral_axis_ab/work `
  --villa-dir ..\_worktrees\villa-axis-ab-current `
  --python C:\path\to\python.exe --phase full --steps 30000
```

The harness records hashes, exact commands, environment information, logs, and
run receipts. It refuses unpinned source commits, PyTorch 2.13+, changed inputs,
or a dataset pair that differs anywhere besides `umbilicus.json`.

`fit_cli_adapter.py` addresses one current-main headless-CLI mismatch without
changing Villa: the CLI invents paths for absent optional assets, while the
fitter treats the simultaneous nonexistent track/shell paths as a request to
load a shell. The adapter substitutes Villa's own existence-probing service
resolver; all configuration, fitting, metrics, and export still execute from
the pinned, unmodified `fit_spiral.py`.

The frozen overrides explicitly select asset-free `grad_mag` mode and zero the
new dense/min-spacing/shell terms on current Villa main. This preserves the
published PCL-only experiment semantics instead of accidentally requesting the
phase bundle's unavailable normal and surface-distance stores.

The independent evaluation workflow is documented in
[`EVALUATION.md`](EVALUATION.md); its planes and decision rule were frozen in
[`EVALUATION_PLAN.md`](EVALUATION_PLAN.md) before any production result was
available. Do not open the generated `private/blind_key.json` until all seven
plane reviews have been recorded.

## Credit and scope

This wrapper reuses the merged Villa fitter, the public PHerc1218 constraint
pack, and Aleksei Drobkov's public manual curve. It does not reproduce those
components. Its new contribution is the controlled production A/B and its
independent downstream evaluation.
