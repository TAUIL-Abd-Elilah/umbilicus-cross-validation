# Umbilicus-13 protocol

> **Superseded 2026-08-16.** This document is the original automatic/manual
> research plan, not the current release claim. Its self-consistency numbers are
> repeatability heuristics, not anatomical accuracy or ground truth, and the
> proposed 13-scroll set was not completed. Current conservative findings and
> withdrawals are in [`README.md`](README.md) and [`audit/README.md`](audit/README.md).

Frozen 2026-08-12, before any picking imagery was generated. Amendments are appended,
never rewritten.

## Goal

Publish an umbilicus curve for each of the 13 Grand-Prize-eligible scrolls, in the
same `umbilicus.json` schema the Spiral fitter already consumes, at an accuracy
comparable to the existing hand-drawn curves.

## Why this accuracy target

The three public reference curves (PHerc0125 / PHerc0211 / PHerc0826, drawn by
Sean Johnson in khartes on 2026-08-08 and posted to `#general`) are internally
noisy. Measuring each interior control point against the chord joining its two
neighbours gives a self-consistency of:

| scroll | median | p90 | max |
|---|---|---|---|
| PHerc0125 | 39.2 | 89.1 | 154.0 |
| PHerc0211 | 31.6 | 114.4 | 1724.0 |
| PHerc0826 | 63.4 | 182.9 | 342.9 |

(full-resolution voxels)

Their author described them as "maybe not exactly perfect umbil but certainly good
enough for a fit". **The target is therefore parity with that noise floor, not
sub-voxel accuracy**: a median agreement at or below ~50 voxels is at the level of
the annotator's own repeatability, and anything much tighter is not measurable
against this reference.

## Control point density

Subsampling each reference curve to N points and re-interpolating onto its own z
samples gives the density required to not lose information:

| N | PHerc0125 median | PHerc0211 median | PHerc0826 median |
|---|---|---|---|
| 8 | 73.9 | 126.9 | 152.0 |
| 16 | 53.2 | 51.1 | 75.2 |
| 24 | 40.7 | 33.1 | 19.0 |
| 32 | 22.6 | 18.4 | 0.0 |

**24–32 control points per scroll** puts interpolation error at or below the
reference noise floor. That is the density this project targets.

## Method

1. **Window anchoring (automatic).** Per z, take the centroid of the largest
   connected bright component at pyramid level 5. Measured distance from centroid
   to reference umbilicus: median 269–394 voxels, max 1104 — so a 3072-voxel
   window centred there always contains the umbilicus.
2. **Picking (visual).** Render a montage of z-slices at level 3 (8 full-res
   voxels per pixel), each panel a 3072-voxel window with a labelled pixel grid.
   The umbilicus is read off as the centre of the innermost winding, the same
   judgement a human makes in khartes.
3. **Curve assembly.** Sort by z, linearly interpolate, and emit the standard
   schema.

## What was tried and rejected

A per-slice **radial-normal-alignment estimator** was implemented first
(`umbilicus_estimator.py`): structure-tensor sheet normals, scored by
`S(u) = sum_p w(p) <n(p), r(p;u)>^2` over an annulus, maximised by grid search.

On PHerc0125, seeded *exactly on* the reference point, it drifted away by a median
of 108 voxels (max 334) with a wide search window, and 82 voxels (max 157) with a
window tight enough that most of the low drift is the constraint rather than the
estimate. Errors from offset seeds reached 538 voxels.

**Conclusion: local sheet orientation alone does not localise the umbilicus in a
crushed scroll to the required accuracy.** The lamellae in these scrolls are not
concentric about the centre, so the criterion has no sharp optimum there. This is
reported as a negative result; the code is kept so the claim is checkable.

## Validation protocol (frozen before picking)

- **Primary validation: PHerc0211 and PHerc0826.** No imagery from either scroll
  has been viewed at the time of freezing. Both will be picked from montages that
  do **not** display the reference curve, and compared afterwards.
- **Secondary: PHerc0125,** disclosed as partially contaminated — one z-slice
  (z=2140) was viewed with the reference point marked while verifying the
  coordinate convention. Its result is reported separately and does not carry the
  headline claim.
- **Metric:** for each reference control point, the distance from the reference
  (y, x) to the picked curve interpolated at that z, in full-resolution voxels.
  Report median / p90 / max per scroll.
- **Success:** median at or below the reference's own self-consistency median for
  that scroll. This is stated before results exist and is not revised afterwards.

## Credit

- The three reference curves and the khartes workflow are Sean Johnson's
  (`@Bruniss`), posted in `#general` on 2026-08-08.
- PHerc1218 has an existing public umbilicus in `IyanDopico/vesuvius-sheet-tools`;
  it is used as a fourth independent cross-check and credited.
- The `umbilicus.json` schema is Villa's, consumed by
  `volume-cartographer/scripts/spiral/umbilicus.py:json_umbilicus_z_to_yx`.

## Amendment 01 — 2026-08-12, after the first blind measurement

A single-pass visual pick of PHerc0211 (16 points, 4096-voxel window at level 3,
10.7 full-res voxels per panel pixel, reference not displayed) was scored against
the reference **before** any reference imagery was viewed:

| | median | p90 | max |
|---|---|---|---|
| blind single-pass picks | 432.0 | 1112.8 | 1498.9 |
| reference's own noise | 31.6 | 114.4 | 1724.0 |

**Verdict: MISS.** The frozen target was median <= 31.6; the result is 13.7x that.
The error is strongly localised — the six worst points all lie in z 12000-12900,
where the estimate is off by ~1300-1500 voxels.

This blind number stands on the record and is not revised.

Consequence for the validation plan: to diagnose the failure the reference curve
must now be displayed over PHerc0211 imagery, which contaminates PHerc0211 as a
validation target. Amending the frozen plan accordingly:

- **PHerc0211** moves from primary validation to *calibration*. Its blind 432
  result is retained and reported; no post-calibration re-pick of PHerc0211 may
  be presented as a validation result.
- **PHerc0826** becomes the sole remaining clean primary validation scroll. No
  PHerc0826 imagery has been viewed at the time of this amendment. It will be
  picked blind once, after calibration, and scored once.
- **PHerc0125** remains secondary and partially contaminated as already disclosed.

This leaves exactly one untouched validation target, so the headline accuracy
claim rests on a single blind scroll. That is a real weakness of the design and
is to be stated plainly rather than worked around by re-picking a seen scroll.

## Amendment 02 — 2026-08-12, diagnosis of the picking failure

The reference curve was overlaid on the PHerc0211 montage, and four z were then
re-rendered at 4 full-res voxels per pixel *centred on the true umbilicus*
(`_zoom_check.png`, z = 11833 / 12941 / 6293 / 1862).

**At z=11833 and z=12941 the true umbilicus sits in ordinary, gently curving
lamellae with no eye, cavity, or other local landmark.** The visually striking
features on those slices — a large fold, a crosshatched damage patch — are
elsewhere, and are what the blind picks were drawn to. Only z=1862 shows a
recognisable spiral centre at the true location.

This single observation explains both failures recorded above:

- the radial-normal estimator has no sharp optimum at the umbilicus because the
  lamellae there are not locally concentric; and
- static-montage visual picking misses for the same reason — on a crushed scroll
  the umbilicus is a *topological* property of how the windings connect, not a
  local appearance feature of one z-slice.

It also explains why the reference was drawn in khartes: an interactive viewer
lets an annotator start from a slice where the centre *is* obvious and carry it
through z by continuity, panning and zooming as the body deforms. The reference's
own median lateral step is only 89 voxels between control points ~188 z apart, so
continuity is a strong constraint — but it is a *sequential* one, unavailable to a
method that treats each slice independently.

**Consequence:** per-slice picking, automatic or visual, is the wrong instrument.
The picking itself moves to interactive khartes annotation. What this project
contributes is the surrounding apparatus — surgical slice access, the montage and
overlay tools, the reference-validated accuracy harness, the schema writer, and
these two negative results — plus the finished 13-scroll set that comes out of it.

## Amendment 03 — 2026-08-12, third approach also rejected

Amendment 02 concluded the umbilicus is topological, which suggested a topological
instrument: the **Poincaré index** of the sheet-orientation field. Scroll lamellae
form a line field like fingerprint ridges, and a winding centre is a +1 singularity
— an invariant that should survive the deformation that defeated the radial score.

Implemented in `poincare.py` (doubled-angle smoothing, multi-radius loops, coherence
masking). Measured against the references, with the body-centroid seed as baseline,
over 8 z per scroll:

| scroll | seed median | Poincaré core median |
|---|---|---|
| PHerc0211 | 316.7 | 986.5 |
| PHerc0826 | 385.2 | 1430.4 |
| PHerc0125 | 264.7 | 800.8 |

**Rejected: it is 2.5-3.7x worse than doing nothing clever.**

One detail is worth recording rather than burying. At PHerc0211 z=8793 the core
landed **31.5 voxels** from the reference — better than any other method tried, at
any z. So the singularity signal genuinely exists at the umbilicus; it is simply not
the *global* maximum of the index field, because damage, folds and delamination
generate competing singularities that are often stronger. A tracker that constrained
the search by z-continuity from a seeded slice might recover it. That is future work
and is not claimed here.

**Standing conclusion after three attempts (radial alignment, static visual picking,
Poincaré index): automatic umbilicus localisation on crushed prize scrolls from CT
intensity alone is unsolved.** The best automatic estimate in this repository remains
the body centroid at ~300 voxels median. This is consistent with the maintainers'
own suggestion in `#general` that automation should come from the lasagna normal
field rather than from raw CT — a route this project has not attempted.

No further automatic variants will be tried under this protocol. The finished
curves are produced by manual correction in khartes, seeded by the centroid curve.

## Amendment 04 — 2026-08-12, PHerc1218 is not an independent reference

The PHerc1218 curve from `IyanDopico/vesuvius-sheet-tools` was initially treated as
a fourth, out-of-family reference, and the seed scored a median of **46.5 voxels**
against it — six times better than against any human curve.

That number is not an accuracy measurement. Reading the producing script,
`scripts/constraints/make_umbilicus.py`, its own docstring states it "takes the
papyrus centroid of each slice as the umbilicus position, smooths the z->(y,x)
series with a running median". **That is the same algorithm as this repository's
seed.** The 46.5 figure measures agreement between two implementations of one
method, not agreement with the true umbilicus.

Corrections:

- PHerc1218 is **removed from the accuracy validation set**. It is retained only as
  an implementation cross-check, which it passes.
- The count of scrolls holding a human-drawn umbilicus is **3, not 4**. PHerc1218
  needs a manual curve like the other nine.
- The seed's honest measured accuracy is therefore **289-382 voxels median against
  three human references**, with no result better than that from any source.

Had this not been checked, the release would have claimed independent validation at
46.5 voxels. Provenance of a reference must be read, not inferred from the fact that
a different person published it.

## Amendment 05 — 2026-08-12, the lasagna route, and the final answer on automation

Both maintainers suggested automating from the lasagna normal field rather than raw
CT (`#general`: Bruniss, "Could prob automate w/ the lasagna normals?"; waldkauz,
"We could port it to lasagna normals, should be more robust"). The published
lasagna predictions do exist for these scrolls, under
`<scroll>/representations/predictions/lasagna/`, as `nx` / `ny` / `cos` / `grad_mag`
OME-Zarr stores (blosc, 32^3 chunks, levels from "2").

Feeding those trained normals into the same radial-convergence score that failed on
structure-tensor normals **does help**: on PHerc0211, per-slice median error fell
from the centroid seed's 299.6 to **209-232 voxels**.

A dynamic-programming tracker (`track.py`) was then added to combine the per-slice
score grids under a continuity prior, on the reasoning that confident slices should
pin the ambiguous ones. Swept over cached grids:

| continuity | median | p90 | max |
|---|---|---|---|
| none (lambda=0) | **209.3** | 579.1 | 1352.2 |
| any lambda >= 0.25 | 269.4 | 975.1 | 1224.0 |

**Continuity made it worse, not better.** Two things follow. First, a caveat on the
sweep itself: every lambda >= 0.25 returns an identical path, which means the
penalty scale is mis-parameterised relative to the normalised scores and the sweep
only really compares "no prior" against "prior dominates" — it does not rule out
some well-scaled middle. Second, and more informative, the assumption behind the
tracker was wrong. The lasagna evidence is not sharp-on-some-slices and
wrong-on-others; it is *uniformly mediocre*, so there are no confident slices to
propagate from, and smoothing merely drags the better slices toward the worse.

### Final tally

| method | median error vs hand-drawn reference |
|---|---|
| reference's own noise (the bar) | **31.6 - 63.4** |
| lasagna normals, per-slice | **209.3** |
| lasagna normals + DP continuity | 269.4 |
| body-centroid seed | 299.6 |
| blind visual montage picking | 432.0 |
| Poincaré index of the sheet field | 800.8 - 1430.4 |
| structure-tensor radial convergence | drifts 82-334 off truth when seeded on it |

Six approaches. The best automatic result is **209 voxels, about 6.6x the accuracy
bar**. Automatic umbilicus localisation is not solved here, and no further variants
will be attempted under this protocol.

The lasagna per-slice estimator is nonetheless kept and shipped: at 209 voxels it is
a meaningfully better starting curve than the 300-voxel centroid seed, and it is a
published, reproducible automatic baseline that did not previously exist.

## Amendment 06 — 2026-08-12, the lasagna estimate across all three references

Amendment 05 quoted the lasagna estimator at 209 voxels from PHerc0211 alone. Running it on all
13 scrolls and scoring against all three hand-drawn references gives a less flattering and more
honest picture:

| scroll | centroid seed | lasagna estimate | change |
|---|---|---|---|
| PHerc0125 | 289.4 | **151.9** | -48% |
| PHerc0211 | 299.6 | **209.4** | -30% |
| PHerc0826 | 381.7 | **409.1** | **+7% (worse)** |

**The estimator is inconsistent, not uniformly better.** It roughly halves the error on
PHerc0125, cuts a third on PHerc0211, and is slightly worse than doing nothing on PHerc0826.
Quoting "209 voxels" as the method's accuracy would have been generalising from the one scroll
that happened to be measured first. The defensible statement is: **the lasagna estimate is
better than the centroid seed on two of three scrolls and worse on the third, spanning
152-409 voxels against a 32-63 voxel bar.**

Both curve sets ship. Neither is presented as a finished umbilicus, and the per-scroll numbers
above travel with them so an annotator knows the starting curve may be no better than the seed.

Note on blindness: this comparison reads a *number* derived from the PHerc0826 reference, not
PHerc0826 imagery. The reserved blind test — a human visual pick on PHerc0826 without viewing
the reference curve — remains available and uncontaminated.

## Amendment 07 — 2026-08-12, the sequential picking test. Decisive negative.

The one untried instrument was *sequential* picking: batches of four z, each anchored on
the running track from prior batches carried forward along the seed's drift, so every panel
centre is a prediction from earlier decisions. This is the property khartes gives a human and
that static montages lack. Implemented in `sequential_pick.py` / `record_picks.py`.

Run blind on PHerc0826 — the only scroll whose imagery had never been displayed. 24 points,
4096-voxel windows at 8 full-res voxels per pixel, reference never rendered. Picks frozen at
SHA-256 `6557e2d8de80868e21668288490543b7db909429755d4fc1402c3dac7429b66f` before scoring.

| | median | p90 | max |
|---|---|---|---|
| **the bar** (reference self-consistency) | **63.4** | 182.9 | 342.9 |
| centroid seed | 381.7 | 778.9 | 1127.0 |
| lasagna estimate | 409.1 | 879.8 | 1244.9 |
| **sequential blind picks** | **522.8** | 880.1 | 1047.9 |

**Worse than every automatic baseline, and worse than the earlier static-montage attempt
(432 on PHerc0211).** Sequential anchoring did not help.

The breakdown by the confidence I assigned at pick time is the finding that settles it:

| my confidence | n | median error |
|---|---|---|
| high | 2 | 296.1 |
| medium | 19 | 596.7 |
| low | 19 | 559.5 |
| **none** (pure anchor default, no judgement) | 7 | **310.6** |

**The points where I made no judgement scored roughly twice as well as the points where I
did.** My visual picks are not merely uninformative on this data — they are anti-informative:
every act of judgement moved the curve away from the truth, and the best thing I did all run
was decline to decide. Confidence was also uncorrelated with accuracy, so I cannot even filter
my own picks.

Combined with Amendment 02 (at the true umbilicus the slice shows ordinary lamellae, and the
salient features are folds and damage elsewhere), the mechanism is clear: I reliably detect the
wrong structures, and doing so sequentially just propagates the error.

**Standing conclusion after seven approaches: this agent cannot produce these curves.** Not by
automatic estimation, and not by visual picking, sequential or otherwise. The remaining path is
manual annotation by a human in an interactive viewer. No further picking attempts will be made
under this protocol; PHerc0826's blind validation slot is now spent and cannot be reused.
