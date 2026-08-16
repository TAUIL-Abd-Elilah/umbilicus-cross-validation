# Independent umbilicus review

Six independently hand-drawn umbilicus curves for Herculaneum scrolls, plus a
reproducible comparison with [Aleksei Drobkov's public set](https://github.com/AlexeyDrobkovStrikesBack/herculaneum-umbilici).

The original ten-scroll drawing pass stopped at 6/10 when Aleksei's complete set
was published. The six finished curves are still useful as independent second
annotations: they reveal where two reviewers followed different folds and where
expert review is most valuable.

**Current safety status:** PHerc1203 is withdrawn from recommended use after
AI-assisted exact-CT review found four separated regions where the public curve
follows the scroll core more consistently. Its original annotation remains only
as an audit artifact. The adaptive screen covers PHerc0191, PHerc0257, PHerc0800, PHerc0813,
and the preregistered PHerc0358 v2 candidate: all 149 adjacent-control intervals
were reviewed, 10 need an added control, and 8 remain unresolved. All six manual
JSONs remain unchanged historical annotations.

## What is included

- Six Villa-compatible curves in [`manual/`](manual/), licensed CC BY 4.0.
- Hash-bound QC manifests recording the reviewer, CT stream, fresh-project
  reimport, curve hash, and local evidence hashes.
- A pinned same-z comparison in [`audit/`](audit/).
- Exact-CT disagreement and midpoint-density review tools.
- Reproducible downstream screens in [`audit/downstream/`](audit/downstream/).

| Scroll | Controls | Median disagreement | Largest disagreement |
|---|---:|---:|---:|
| PHerc0191 | 30 | 4.38 mm | 18.31 mm at z=15480 |
| PHerc0257 | 31 | 2.95 mm | 7.55 mm at z=9552 |
| PHerc0358 | 31 | 1.76 mm | 10.91 mm at z=9944 |
| PHerc0800 | 31 | 3.70 mm | 11.35 mm at z=17816 |
| PHerc0813 | 31 | 4.81 mm | 12.71 mm at z=6616 |
| PHerc1203 | 40 | 2.18 mm | 12.00 mm at z=6197 |

These distances identify review locations. They do **not** identify which curve
is correct.

## What the CT review shows so far

These are conservative internal, AI-assisted triage findings from exact-volume
overlays. They are not experienced-user acceptance or anatomical ground truth.

- **PHerc0358 z=5500:** public curve favored; our point makes an isolated
  excursion to an outer cusp.
- **PHerc0800 z=4856 and z=17816:** public curve provisionally favored.
- **PHerc0191 z=15480:** visual CT review favors ours, while the winding-order
  fixture favors the public curve. Unresolved.
- **PHerc0257 z=9552:** both candidate folds persist through nearby slices.
  Unresolved.
- **PHerc0813 z=6616 and z=9296:** ours improves the local radial score, but the
  public curve performs better over the full 30-slice screen. Unresolved.
- **PHerc0358 z=9948:** ours is provisionally favored, but the transfer between
  folds needs denser expert review.

No public curve has been replaced. All findings remain review candidates.

PHerc0358 has a preregistered z=5500 correction candidate under
[`audit/corrections/`](audit/corrections/). All 30 of its interpolation intervals
were continuity-supported in the assisted axial and orthogonal screen. It is
still a candidate, not the released curve, until an experienced reviewer accepts
the actual volume overlay.

## Figures

[`audit/comparison_overview.png`](audit/comparison_overview.png) is a triage map:
it shows where the curves diverge, not whether either is accurate. Accuracy must
be reviewed by overlaying both candidates on the exact CT volume and checking
nearby and orthogonal slices. `render_exact_ct_review.py` generates reviewer packs
with:

1. the same CT crop without markers;
2. the same crop with red=independent and cyan=public;
3. equal-scale crops centered on each candidate;
4. marker-free neighboring slices for continuity.

CT pixels are generated locally and are not stored in this repository.

## Adaptive control-density audit

Villa linearly interpolates between umbilicus controls. A fixed count of about 30
controls can be sufficient on straight regions and insufficient on sharp bends.
`audit_midpoint_density.py` renders every adjacent-control midpoint as an
identical marker-free/marked CT pair and ranks XY bends for review. Suspect
intervals are escalated to higher-resolution axial views and candidate-following
XZ/YZ views before a final conservative classification.
The orthogonal renderer expands each window to contain the full candidate
trajectory and preserves the physical z-to-xy aspect ratio.

| Curve | Intervals | Keep linear | Add control | Unresolved |
|---|---:|---:|---:|---:|
| PHerc0191 | 29 | 25 | 2 | 2 |
| PHerc0257 | 30 | 29 | 1 | 0 |
| PHerc0358 v2 candidate | 30 | 30 | 0 | 0 |
| PHerc0800 | 30 | 20 | 7 | 3 |
| PHerc0813 | 30 | 27 | 0 | 3 |
| **Total** | **149** | **131** | **10** | **8** |

The full curve-hash-bound partition, receipt metadata, and claim boundary are in
[`audit/midpoint_density/`](audit/midpoint_density/). `Keep linear` means no
interpolation break was visible in the recorded screens; it is not proof of
anatomical correctness. Added controls still require independent level-0 Khartes
placement and a fresh rerender. Unresolved intervals must remain untouched.

```bash
# Fast whole-curve screen.
python audit_midpoint_density.py --scroll PHerc0813 --level 3

# Re-render flagged intervals at higher resolution before editing.
python audit_midpoint_density.py --scroll PHerc0813 --level 2 \
  --segment 1 --segment 10 --segment 11

# Check the same candidate trajectory in XZ and YZ.
python render_midpoint_orthogonals.py --scroll PHerc0813 --level 3 \
  --segment 1 --segment 10 --segment 11

python verify_midpoint_screening.py
```

The rank is triage, not a correctness score. New controls must be placed from the
exact CT volume; neither another annotator's coordinates nor a spline prediction
is accepted as ground truth. No public, licensed implementation of the recently
described "armwise neutral-spine" method was located, so this repository does not
claim to implement or redistribute it. The dated source-search summary is
in [`audit/neutral_spine_source_check.md`](audit/neutral_spine_source_check.md).

## Reproduce

```bash
git clone https://github.com/AlexeyDrobkovStrikesBack/herculaneum-umbilici external

python compare_independent_curves.py \
  --reference-dir external \
  --reference-revision 57e09a3d6f25773a2e0cad9d21eb97296cef50c8 \
  --reference-url https://github.com/AlexeyDrobkovStrikesBack/herculaneum-umbilici

python plot_independent_comparison.py --reference-dir external
python render_exact_ct_review.py --reference-dir external --scroll PHerc0813 --z 6616
python -m unittest -v test_slicefetch test_longitudinal \
  test_audit_midpoint_density test_render_exact_ct_review \
  test_render_midpoint_orthogonals \
  test_compare_independent_curves test_correction_artifacts \
  test_verify_midpoint_screening
```

The coordinate comparison requires NumPy. Plotting requires Matplotlib. Exact-CT
review packs additionally require Pillow and OpenCV and stream small windows from
the public Vesuvius Challenge volumes.

## Licences

Code: MIT. Six manual curve JSONs and the separate PHerc0358 v2 candidate:
CC BY 4.0, attributed to Abd Elilah. Source CT data is not redistributed here.
