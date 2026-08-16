# Manual umbilicus outputs

This directory is reserved for approved human-corrected curves. Khartes must first export to
`candidates/<scroll>_umbilicus.candidate.json`; never export directly to the final filename.
After fresh-project reimport and full-z human review, `../approve_manual_curve.py` creates
`<scroll>_umbilicus.json` plus `manifests/<scroll>_qc.json`. Automatic seed/estimate files belong
in `../seeds/` and must never be copied here or presented as finished curves.

Each completed output should normally have 24-32 canonical `X,Y,Z` controls. A corrected
40-control lasagna starting curve is also acceptable; do not delete good controls merely to hit
32. Every output must be exported as Villa `control_points` JSON, survive a fresh-project reimport
unchanged, and receive a full-z visual check. Retain representative start/middle/end and
ambiguous-transition screenshots separately. The required role and displayed z must appear as
filename tokens (for example `_start_z0960`); screenshots must decode as PNG/JPEG, be at least
256x256, and the three required views must be distinct and ordered in z.

Approval rejects an exact untouched seed or estimate, a wrong stream/range/schema, missing
screenshots/QC identity/licence, out-of-volume X/Y/Z, inadequate useful-z coverage, and overwrites.
A JSON curve without its matching v2 manifest is not release-ready. Once all ten pass, run
`../verify_manual_release.py`; it rehashes the complete set and evidence, checks one coherent data
licence, and loads every curve through Villa's real Spiral consumer. Only its complete pass may
create `release_manifest.json` with `--write-manifest`. CT-derived screenshots are local QC evidence unless Vesuvius Challenge gives
written redistribution permission; do not broadly archive this tree.

Six independently drawn curves passed the original export/reimport and evidence
checks: PHerc0191, PHerc0257, PHerc0358, PHerc0800, PHerc0813, and PHerc1203. The
original ten-scroll production queue was paused after an independently produced
complete set became public. These files are retained as a second-annotator
cross-validation dataset, not as automatic replacements or ground truth. See
`../audit/README.md`.

**Post-release safety update (2026-08-16):** PHerc1203 is withdrawn from
recommended use. Exact-CT review found four separated regimes where the public
curve follows the scroll core more consistently. The JSON is retained only to
keep the independent annotation and its audit trail reproducible. The enhanced
adaptive screen is complete for PHerc0191, PHerc0257, PHerc0800, PHerc0813, and
the separate preregistered PHerc0358 v2 candidate. It identified 10 intervals
requiring manual control placement and 8 unresolved intervals. None of those
findings has been silently applied to these historical JSONs.
