# August 2026 Progress Prize submission

## Submission status

- **Contribution:** Fail-closed exact-CT audit for Villa umbilicus curves
- **Submitter:** TAUIL Abd Elilah
- **Submission type:** Individual
- **Form status:** submitted; confirmation screenshot supplied 2026-08-17
- **Submitted release:** v0.2.0, published 2026-08-16
- **Submitted release commit:** `8a94faed9eebbeb48e9c624d65cb33818415b2c4`
- **Corrective downstream addendum:** v0.2.1, published 2026-08-17
- **Official deadline:** 2026-08-31, 11:59pm Pacific
- **Submission form:**
  <https://docs.google.com/forms/d/e/1FAIpQLSev2vJobu521iB6OuyehDktzYTEo131F4iUGwt3Qxa9a1fk6A/viewform>
- **Official rules:** <https://scrollprize.org/prizes#progress-prizes>

The submitted Google Form intentionally used a **short** description rather
than duplicating this complete technical dossier. Its public dossier link gives
reviewers the later v0.2.1 corrective addendum as well as the frozen v0.2.0
submission:

<https://github.com/TAUIL-Abd-Elilah/umbilicus-cross-validation/blob/main/AUGUST_2026_PROGRESS_PRIZE_SUBMISSION.md>

The supplied confirmation screenshot records that the submitter selected the
terms agreement and submitted the form.

## Submitted v0.2.0 form answers

These answers are preserved as the submitted snapshot. Do not file a duplicate
form merely to point at v0.2.1.

### 1. Your full name

```text
TAUIL Abd Elilah
```

### 2. Team description

```text
Individual submission by TAUIL Abd Elilah.
```

### 3. Public contribution URLs

```text
Repository:
https://github.com/TAUIL-Abd-Elilah/umbilicus-cross-validation

Frozen v0.2.0 release:
https://github.com/TAUIL-Abd-Elilah/umbilicus-cross-validation/releases/tag/v0.2.0

Six manual Villa-format annotations:
https://github.com/TAUIL-Abd-Elilah/umbilicus-cross-validation/tree/v0.2.0/manual

Adaptive midpoint audit and receipts:
https://github.com/TAUIL-Abd-Elilah/umbilicus-cross-validation/tree/v0.2.0/audit/midpoint_density

Reproducible comparison and downstream checks:
https://github.com/TAUIL-Abd-Elilah/umbilicus-cross-validation/tree/v0.2.0/audit

Complete technical submission dossier:
https://github.com/TAUIL-Abd-Elilah/umbilicus-cross-validation/blob/main/AUGUST_2026_PROGRESS_PRIZE_SUBMISSION.md
```

### 4. Short description of how this increases the probability of reading complete scrolls

```text
Complete-scroll virtual unrolling depends on a reliable umbilicus for the scroll axis and winding geometry. Sparse controls can make linear interpolation leave the intended core or cross folds where the umbilicus bends rapidly with z.

I released six independently drawn Villa-format umbilicus annotations together with a fail-closed exact-CT audit and reproducible comparison tools. The audit checks the midpoint of every adjacent control interval on real Herculaneum CT data, escalates suspicious intervals to higher-resolution axial and candidate-following XZ/YZ views, preserves physical aspect ratio, and records the curve, CT stream, parameters, and fetch status in machine-readable receipts.

All 149 intervals across five screened curves were classified: 131 retain linear interpolation, 10 require an additional manually placed control, and 8 remain unresolved rather than being silently changed. PHerc1203 was withdrawn after the audit found four separated branch-selection failures. The result gives Khartes/Spiral users reusable standard-format annotations, concrete locations requiring correction, and a reproducible workflow for detecting branch hops and inadequate control density before downstream spiral fitting and unrolling.
```

### 5. Terms and conditions

Select **“Yes, I agree”** only after personally reading the official terms.

## Suggested public title

**Fail-closed exact-CT audit and independent umbilicus annotations for Herculaneum scrolls**

## One-paragraph abstract

This contribution publishes six independently drawn Villa-compatible umbilicus
annotations and a conservative audit workflow for detecting failures caused by
sparse control spacing. It checks every adjacent-control midpoint on the exact
public CT volume, escalates suspicious intervals from axial screening to
higher-resolution and candidate-following XZ/YZ views, and fails closed on
unvalidated source-data errors. The completed screen covers 149 intervals across
five curves: 131 were retained, 10 require additional manual controls, and 8 were
left unresolved. The release also contains a pinned same-z comparison with an
independent public annotation set, reproducible downstream proxy checks, a
preregistered PHerc0358 correction candidate, and an explicit withdrawal of
PHerc1203 from recommended use.

## Post-submission PHerc1218 A/B limitation (v0.2.1)

After the form submission, a preregistered production Spiral A/B tested an
external PHerc1218 candidate axis against the stitched-pack baseline. Both arms
used the same three patches, input constraints, full-resolution `z=[5220,6020)`,
seed 1, and 30,000 optimizer steps.

The candidate arm failed the frozen run-health admission thresholds: 91.562% of
relative-PCL points passed against a 94% minimum, and 85.567% of same-winding
points passed against a 91% minimum. A blind exact-CT review recorded 0 candidate
preferences, 3 baseline preferences, and 4 ties. The intrinsic comparison
reversed direction between the two candidate-axis frames, so it could not select
a robust anatomical winner.

The bounded decision is therefore **no PHerc1218 baseline replacement from this
test**. The result does not establish that the baseline is anatomically true.
It tests neither the six released manual curves nor the midpoint-density audit,
so those deliverables remain intact with their original limitations. Full
protocol, source pins, code, artifact hashes, and machine-readable metrics are
in [`downstream/spiral_axis_ab/`](downstream/spiral_axis_ab/).

## Problem addressed

Villa/Spiral represents an umbilicus as sparse `(x, y, z)` controls and linearly
interpolates between them. A fixed control count can work in straight regions but
can fail where `x/y` changes rapidly with `z`. A curve can therefore look
reasonable at its controls while its interpolation crosses a different fold or
unsupported material halfway between them. Such an axis can propagate errors to
winding constraints, spiral fitting, surface tracing, and downstream unrolling.

The contribution turns that general concern into a complete, reproducible audit:

1. inspect every adjacent-control interval, not only the controls;
2. render the exact midpoint from the bound CT stream;
3. compare identical marker-free and marked axial pixels;
4. escalate suspicious intervals at higher resolution;
5. inspect the candidate trajectory in both XZ and YZ;
6. distinguish safe interpolation, insufficient density, and unresolved anatomy;
7. require independent level-0 placement before adding a control.

## Public deliverables

### Manual annotations

Six Villa `control_points` JSON files are public:

| Scroll | Controls | Status after enhanced audit |
|---|---:|---|
| PHerc0191 | 30 | 2 add-control intervals; 2 unresolved |
| PHerc0257 | 31 | 1 add-control interval |
| PHerc0358 | 31 | historical curve retained; separate v2 candidate audited |
| PHerc0800 | 31 | 7 add-control intervals; 3 unresolved |
| PHerc0813 | 31 | 3 unresolved intervals |
| PHerc1203 | 40 | withdrawn from recommended use |

Each historical manual file remains unchanged. The audit does not silently
rewrite published annotations.

### Adaptive midpoint-density audit

| Curve screened | Intervals | Keep linear | Add control | Unresolved |
|---|---:|---:|---:|---:|
| PHerc0191 | 29 | 25 | 2 | 2 |
| PHerc0257 | 30 | 29 | 1 | 0 |
| PHerc0358 v2 candidate | 30 | 30 | 0 | 0 |
| PHerc0800 | 30 | 20 | 7 | 3 |
| PHerc0813 | 30 | 27 | 0 | 3 |
| **Total** | **149** | **131** | **10** | **8** |

Decision meanings:

- **Keep linear:** no interpolation break remained visible after the recorded
  review stages. This is not a claim of anatomical ground truth.
- **Add control:** the current linear interpolation appears inadequate. The
  replacement coordinate must still be placed independently in level-0 Khartes
  and both new intervals must be rerendered.
- **Unresolved:** the available views do not establish one defensible
  continuation, so the curve remains unchanged.

### Exact-CT and orthogonal review tools

- `audit_midpoint_density.py` renders every axial midpoint and selected
  higher-resolution escalations.
- `render_midpoint_orthogonals.py` renders candidate-following XZ and YZ views.
- `render_exact_ct_review.py` compares independent/public candidates on identical
  pixels with marker-free context.
- Orthogonal windows expand to contain the complete candidate trajectory.
- Orthogonal displays preserve the physical z-to-xy aspect ratio.
- A Zarr 404 is accepted only after validating that the level's declared fill
  value is zero; other fetch failures abort.
- Empty source panels and corrupt cache tiles abort rather than producing
  plausible-looking evidence.

CT-derived images are generated locally and are not redistributed. Public JSON
receipts bind curve hashes, source streams, review parameters, selected segment
numbers, valid fill-chunk counts, and zero failed source chunks.

### Independent comparison

The release compares the six independent curves with Aleksei Drobkov's public
set at pinned revision
`57e09a3d6f25773a2e0cad9d21eb97296cef50c8`. Same-z lateral distance is used to
find review locations; it is not treated as ground truth.

| Scroll | Median disagreement | Largest disagreement |
|---|---:|---:|
| PHerc0191 | 4.38 mm | 18.31 mm at z=15480 |
| PHerc0257 | 2.95 mm | 7.55 mm at z=9552 |
| PHerc0358 | 1.76 mm | 10.91 mm at z=9944 |
| PHerc0800 | 3.70 mm | 11.35 mm at z=17816 |
| PHerc0813 | 4.81 mm | 12.71 mm at z=6616 |
| PHerc1203 | 2.18 mm | 12.00 mm at z=6197 |

The comparison exposed actionable regions and contributed to the PHerc1203
withdrawal. It deliberately reports disagreement rather than automatically
declaring either annotation correct.

### PHerc0358 v2 candidate

The preregistered candidate changes only the z=5500 control, from `(4500, 4650)`
to `(4162, 3821)`, using interpolation between the independent curve's adjacent
controls rather than copying a public coordinate.

- candidate SHA-256:
  `4ff05537741cef16cad3bbf40597f3ae180d42f6ed204d3358824bca35d3856d`
- Villa loader round-trip: 31/31 controls, maximum coordinate error 0
- assisted midpoint continuity screen: 30/30 keep-linear
- status: candidate only, pending experienced exact-volume acceptance

The descriptive radial-anisotropy proxy became worse for this candidate, while
same-z disagreement statistics improved. Both findings are published because the
proxy is not ground truth and can favor the wrong V-shaped cusp.

### PHerc1203 withdrawal

Exact-CT review found four separated branch-selection failures near z=6198,
7508, 9560, and 15812. This indicates a curve-wide problem that cannot be fixed
by four local nudges. PHerc1203 therefore remains available only as a reproducible
independent annotation/audit artifact and is withdrawn from recommended use.

## Real-data inputs

The audit uses these public Vesuvius Challenge OME-Zarr volumes:

| Scroll | Volume |
|---|---|
| PHerc0191 | `20250821151635-9.362um-1.2m-113keV-masked.zarr` |
| PHerc0257 | `20250821151750-9.362um-1.2m-113keV-masked.zarr` |
| PHerc0358 | `20250821151737-9.362um-1.2m-113keV-masked.zarr` |
| PHerc0800 | `20250521135224-8.640um-1.2m-116keV-masked.zarr` |
| PHerc0813 | `20250821151723-9.362um-1.2m-113keV-masked.zarr` |
| PHerc1203 | `20250820131727-9.362um-1.2m-113keV-masked.zarr` |

## Reproduction

Clone the submitted release and the pinned comparison repository:

```bash
git clone --branch v0.2.0 \
  https://github.com/TAUIL-Abd-Elilah/umbilicus-cross-validation.git
cd umbilicus-cross-validation

git clone https://github.com/AlexeyDrobkovStrikesBack/herculaneum-umbilici external
git -C external checkout 57e09a3d6f25773a2e0cad9d21eb97296cef50c8
```

Verify the complete midpoint partition and archived downstream receipts:

```bash
python verify_midpoint_screening.py
python audit/downstream/validate_receipts.py audit/downstream
```

Generate an axial midpoint screen and orthogonal escalation:

```bash
python audit_midpoint_density.py --scroll PHerc0813 --level 3

python audit_midpoint_density.py --scroll PHerc0813 --level 2 \
  --segment 1 --segment 10 --segment 11

python render_midpoint_orthogonals.py --scroll PHerc0813 --level 3 \
  --segment 1 --segment 10 --segment 11
```

Reproduce the coordinate comparison:

```bash
python compare_independent_curves.py \
  --reference-dir external \
  --reference-revision 57e09a3d6f25773a2e0cad9d21eb97296cef50c8 \
  --reference-url https://github.com/AlexeyDrobkovStrikesBack/herculaneum-umbilici
```

## Verification performed before release

- 50/50 selected unit and integration tests passed.
- 149/149 midpoint intervals form a complete, non-overlapping decision partition.
- All non-keep intervals have orthogonal evidence receipts.
- Corrected orthogonal packs were independently rereviewed: 38/38, with no
  verdict changes after removing clipping and display distortion.
- 23/23 public JSON artifacts parsed successfully.
- Both archived downstream receipts passed their arithmetic validators.
- PHerc0358 v2 passed the actual Villa loader round-trip with zero error.
- Public receipts contain portable paths rather than machine-local paths.
- No source CT pixels, cache files, Khartes projects, credentials, or private
  third-party material are in the release.
- Remote tag `v0.2.0` and `main` were verified to point to commit
  `8a94faed9eebbeb48e9c624d65cb33818415b2c4`.

## Integration and usefulness

- Curves use Villa's existing `control_points` JSON schema and level-0
  `(x, y, z)` convention.
- The annotations load through Villa's Spiral consumer.
- The workflow accepts the public OME-Zarr streams directly.
- Receipts are ordinary JSON and can be consumed by CI or downstream tooling.
- The output tells an operator exactly which intervals can remain linear, which
  need a new control, and which should not be edited without more evidence.
- The same workflow can audit future manual or automatically generated
  umbilicus curves before they are used for fitting or unrolling.

## Claim boundary and limitations

- There is no public anatomical ground truth for these scroll umbilici.
- `keep_linear` validates visible interpolation continuity in the recorded
  screens, not the absolute correctness of an entire curve.
- Exact placement for the 10 add-control intervals remains manual work in
  level-0 Khartes, followed by rerendering.
- The 8 unresolved intervals remain unchanged pending experienced interactive
  review.
- Candidate-following planes are review aids; proximity to their red trajectory
  is not itself evidence of correctness.
- Winding-order and radial-anisotropy measurements are exploratory proxies, not
  accuracy scores.
- The interval triage is explicitly labeled AI-assisted and remains available
  for experienced-user review.

## Licensing and attribution

- Source code: MIT.
- Six manual curve JSONs and the PHerc0358 v2 candidate: CC BY 4.0.
- Curve attribution: Abd Elilah, “Independent Herculaneum umbilicus
  annotations” (2026).
- Public comparison set: Aleksei Drobkov,
  <https://github.com/AlexeyDrobkovStrikesBack/herculaneum-umbilici>.
- Schema/consumer: ScrollPrize Villa.
- Manual editor: Khartes.
- CT data: Vesuvius Challenge; source pixels are not redistributed.

## Short Discord announcement

```text
I released six manual umbilicus annotations plus an exact-CT audit and comparison tools. The audit covers 149 intervals: 131 keep, 10 need extra controls, and 8 are unresolved. Feedback from experienced Khartes/Spiral users is welcome:
https://github.com/TAUIL-Abd-Elilah/umbilicus-cross-validation/releases/tag/v0.2.0
```

## Final submission checklist

- [x] Match the form's full name: `TAUIL Abd Elilah`.
- [x] Open the official August 2026 form while signed into the desired account.
- [x] Copy the four answers above without changing the numerical claims.
- [x] Read the official terms and personally select the agreement checkbox.
- [x] Submit before 2026-08-31 at 11:59pm Pacific.
- [x] Retain the supplied form-confirmation screenshot.
- [ ] Retain the edit-response link, if Google supplied one.
- [ ] Recheck every submitted URL in a private/incognito browser window.
- [ ] Keep the repository and release public through judging.
- [ ] Respond to reviewer questions and record community feedback as issues.
