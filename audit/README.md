# Six-scroll independent comparison

This is a coordinate-only comparison between six curves drawn independently by
Abd Elilah and the corresponding files in Aleksei Drobkov's
[`herculaneum-umbilici`](https://github.com/AlexeyDrobkovStrikesBack/herculaneum-umbilici)
at revision `57e09a3d6f25773a2e0cad9d21eb97296cef50c8`.

## Result

| Scroll | Ours / public controls | median | p95 | max (z) |
|---|---:|---:|---:|---:|
| PHerc0191 | 30 / 22 | 4.377 mm | 16.738 mm | 18.311 mm (15480) |
| PHerc0257 | 31 / 29 | 2.945 mm | 6.702 mm | 7.548 mm (9552) |
| PHerc0358 | 31 / 31 | 1.758 mm | 7.670 mm | 10.913 mm (9944) |
| PHerc0800 | 31 / 28 | 3.700 mm | 10.068 mm | 11.350 mm (17816) |
| PHerc0813 | 31 / 29 | 4.809 mm | 11.391 mm | 12.706 mm (6616) |
| PHerc1203 | 40 / 31 | 2.184 mm | 10.528 mm | 12.001 mm (6197) |

These values establish substantial inter-annotator uncertainty. They do not say
which curve is right. `comparison_summary.json` marks spaced maxima as
`requires_exact_ct_review`; that status is deliberately not “error” or
“correction.” The 1.81 mm reporting line is inherited from the public release's
own downstream sensitivity estimate and is used only to organize disagreement
bands, not as a ground-truth accuracy threshold.

## Exact-CT adjudication status

The findings below are conservative internal, AI-assisted triage from exact-volume
overlays. They remain pending experienced-user review and are not anatomical
ground truth.

- **PHerc0813:** two regions reviewed. The public controls at z=6616
  `(4748, 5784)` and z=9296 `(5710, 3978)` lie on different external branches in
  candidate-following orthogonal views. The independently drawn curve follows a
  continuous inner turning seam at approximately `(4270, 4514, 6616)` and
  `(4711, 3782, 9296)`. Local radial-anisotropy scores improve at both locations,
  but the public curve scores better over the full 30-slice PHerc0813 screen.
  These are unresolved local review candidates, not silently applied edits.
- **PHerc0191:** visual exact-CT inspection at the maximum disagreement z=15480
  favors the independent point near `(4884, 3966)` over the public point near
  `(3491, 5338)`. However, the neutral traced-arc winding-order fixture strongly
  favors the public curve across its z=14520–16440 stack. The evidence conflicts;
  no correction is claimed.
- **PHerc0257:** unresolved at z=9552. The independent curve follows an upper
  turning pocket and the public curve follows a lower persistent folded column.
  Both branches persist across nearby slices, so neither can be rejected from the
  current evidence.
- **PHerc0358:** the public curve is strongly favored at z=5500; the independent
  point is an isolated outer-cusp excursion. A preregistered candidate replaces
  only that point using interpolation between its independent neighbors. At
  z=9948, the independent branch is provisionally favored but remains ambiguous.
- **PHerc0800:** the public curve is provisionally favored at both z=4856 and
  z=17816. No correction has been promoted.
- **PHerc1203:** exact CT strongly favors the public branch in four separated
  regimes (near z=6198, 7508, 9560, and 15812). The independent PHerc1203 curve
  is withdrawn from recommended use and would require a full redraw; four local
  nudges would not address a curve-wide branch-selection problem.

## Adaptive midpoint-density status

The audit now checks the exact linear midpoint of every adjacent control pair,
because fixed 30-control spacing can miss sharply bent regions. All 149 intervals
across the five viable curves were screened axially; suspect intervals were
rerendered at level 2 and then in candidate-following XZ/YZ sections.

| Curve | Intervals | Keep linear | Add control | Unresolved |
|---|---:|---:|---:|---:|
| PHerc0191 | 29 | 25 | 2 | 2 |
| PHerc0257 | 30 | 29 | 1 | 0 |
| PHerc0358 v2 candidate | 30 | 30 | 0 | 0 |
| PHerc0800 | 30 | 20 | 7 | 3 |
| PHerc0813 | 30 | 27 | 0 | 3 |
| **Total** | **149** | **131** | **10** | **8** |

This is AI-assisted visual triage, not experienced-user acceptance or anatomical
ground truth. No replacement coordinates were inferred from another annotation,
and no source curve was modified. Exact decisions and curve-bound receipt metadata are in
[`midpoint_density/`](midpoint_density/).

## Exploratory downstream comparison

These are proxy measurements, not ground truth, and they do **not** establish that
the six independent curves are globally better. The public implementation was
reproduced to numerical precision before substituting either curve set.

| Scroll | Pairwise public/ours winding-order fixture | Radial-anisotropy mean (ours − public) | ours wins |
|---|---:|---:|---:|
| PHerc0191 | public 0.912, ours 0.821 | +0.03345 | 4/6 |
| PHerc0257 | not available | +0.00187 | 4/6 |
| PHerc0358 | public 0.899, ours 0.899 | −0.00624 | 3/6 |
| PHerc0800 | not available | −0.03408 | 2/6 |
| PHerc0813 | not available | −0.06137 | 1/6 |
| PHerc1203 | public 0.897, ours 0.897 | −0.04227 | 3/6 |

The six-slice radial screen is descriptive: slices are clustered, so no p-value
is attached. Pooled, ours wins 17/36 slices and has mean difference −0.01811.
On the full fixed 30-slice PHerc0813 screen, public mean q is 0.17433 versus
0.14910 for ours. At the two acknowledged suspect controls, ours improves locally
(z6616: 0.11390 vs 0.08451; z9296: 0.08695 vs 0.05990), demonstrating why local
adjudication and whole-curve performance must be reported separately.

CT-derived panels are not committed because source CT terms are handled
separately. The numerical report binds both inputs by SHA-256, allowing reviewers
with source-volume access to reproduce the coordinate comparison and inspect the
same locations.

## Reproduce

From this repository root:

```bash
git clone https://github.com/AlexeyDrobkovStrikesBack/herculaneum-umbilici external
python compare_independent_curves.py \
  --reference-dir external \
  --ours-revision 3a1d8aa1811f6f1428e76513feeabb50535e56d2 \
  --reference-revision 57e09a3d6f25773a2e0cad9d21eb97296cef50c8 \
  --reference-url https://github.com/AlexeyDrobkovStrikesBack/herculaneum-umbilici
python plot_independent_comparison.py --reference-dir external
python -m unittest -v test_compare_independent_curves.py
```

`comparison_overview.png` is coordinate-only: left panels show both XY
trajectories and right panels show same-z separation in millimetres.
