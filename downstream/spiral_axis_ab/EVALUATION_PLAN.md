# Frozen evaluation plan

Frozen at `2026-08-16T20:50:10Z`, while the baseline production fit was still
running and before either production result was inspected.

## Exact CT review planes

Render both fitted winding families on the same PHerc1218 CT slices at full
resolution z:

`5264, 5408, 5536, 5664, 5792, 5872, 5952`

These planes were selected from the input geometry, not output quality: they
cover the beginning and end of the window, patch boundaries/interiors, and the
precomputed peak axis disagreement near z=5872. Use identical crop, contrast,
line width, winding range, and colours for both arms. Hide the arm identity as
`A`/`B` until the review record is complete.

Record per-plane observations for continuous sheet following, crossings,
doubled or missed layers, and obvious departures from visible CT laminae. Do
not infer quality from the axis line alone.

## Quantitative checks

1. Apply the preregistered run-health gates to both arms. Constraint
   satisfaction is secondary because the baseline axis and constraints share
   a label source.
2. Run the public `Nicodol/spiralcheck` intrinsic evaluator at commit
   `d1b50e2957409a870225fb9f5dcc5e25f7a0f9da` on both exported winding
   families, using each arm's own axis. Report crossings, collapsed gaps,
   inflated gaps, checked-bin denominators, and median pitch side by side.
3. If an exact-CT surface-support scorer is used, report its definition and
   coverage and keep it separate from the intrinsic metrics. Credit reused
   public code and pin its commit.

## Decision rule

Call an arm better only if the blinded CT review and at least one independent
geometry measure agree without a material admission-gate failure. Otherwise
report neutral or inconclusive. A technically successful fit is not by itself
an accuracy claim.
