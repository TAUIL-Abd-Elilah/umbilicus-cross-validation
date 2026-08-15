# Manual umbilicus publication checklist

Status: not publishable yet. PHerc1203 is approved locally (1/10); nine
human-corrected outputs and the aggregate release manifest are still missing.

## Coherent deliverable

First publishable unit: the ten new human-corrected curves that fill the missing prize-scroll
coverage. Strongest final unit: a downloadable 13-curve set under clear release terms.

There are two legitimate routes to that final unit:

1. **Preferred:** after the missing ten pass QC, the user independently redraws PHerc0125,
   PHerc0211, and PHerc0826. This adds roughly 19 minutes at the maintainer's reported timings and
   produces a coherent 13-curve set owned by the submitter. PHerc0826 must remain a user-only pass;
   this agent must not open its imagery or reference.
2. Publish the ten new curves plus a 13-row index whose other three rows credit Sean Johnson's
   pre-existing curves. Each external row needs a stable public URL, or Sean's explicit permission
   and licence terms to bundle a copy. The signed Discord CDN attachment URLs are not durable; on
   2026-08-12 the unsigned PHerc0125/PHerc0211 URLs returned HTTP 404 and exact GitHub code search
   found no published copies.

Do not copy the three local validation files into a public release without permission. If neither
route is complete, describe the release as the ten missing curves rather than a downloadable
13-curve bundle.

The local `reference/` directory is validation material, not part of the prospective release.
Its files are not covered by any licence selected for this project's code or new curves.

## Allowed promotion path

The manual release has exactly one promotion path:

1. Khartes exports `manual/candidates/<scroll>_umbilicus.candidate.json`.
2. A human reimports it in a fresh project on the exact CT stream, performs the full-z/transition
   review, and stores the required local QC screenshots.
3. `approve_manual_curve.py` validates the candidate and creates the final JSON plus hash-bound
   manifest without overwriting either.
4. After all ten curves pass individually, `verify_manual_release.py` rehashes every candidate,
   curve, manifest, and screenshot; enforces one data licence; and evaluates every canonical
   control through Villa's real `json_umbilicus_z_to_yx` loader. Only a complete pass may write
   `manual/release_manifest.json` with `--write-manifest`.

Do **not** run the workspace-root `build_umbilicus_publication_package.py` or
`verify_umbilicus_publication_readiness.py` for this deliverable. They are legacy tools for the
automatic pipeline, can traverse reference/held-out material outside the protected manual scope,
and do not implement the candidate-first human-QC contract. Their output cannot approve a manual
curve.

## Gate for each new curve

- Khartes working export named
  `manual/candidates/<scroll>_umbilicus.candidate.json`; never export directly to the final path.
- After fresh-project/full-z human QC, `approve_manual_curve.py` creates both
  `manual/<scroll>_umbilicus.json` and `manual/manifests/<scroll>_qc.json`. The approver rejects an
  exact untouched automatic seed/estimate and refuses overwrite. A curve without its matching
  manifest is not approved.
- Canonical integer `X,Y,Z` Villa `control_points`, unique z values, normally 24-32 controls;
  a fully corrected 40-control lasagna starting curve is acceptable.
- Every X/Y/Z control lies inside the exact CT volume, and the curve spans at least the central
  80% of the useful manual bracket.
- Useful body range inspected without unchecked endpoint extrapolation.
- Fresh-project reimport against the same public CT stream preserves every canonical control and
  the displayed interpolation.
- Full-z visual review, including start, middle, end, every ambiguous transition, and every
  original score-0 seed location.
- Representative screenshots retained locally with scroll ID, CT version, z coordinate, and
  whether the view is routine or ambiguous. The source-data terms prohibit redistribution without
  written approval, so do not commit CT-derived screenshots publicly; use an organizer-approved
  channel or obtain written permission first.
- The `_start`, `_middle`, and `_end` filename roles and displayed `z<integer>` tokens are all
  present; required views are distinct and ordered in z; every evidence file decodes as its
  declared PNG/JPEG type and is at least 256x256.
- Final JSON SHA-256, byte size, control count, z minimum/maximum, CT URL/version, reviewer, and
  review time recorded in the release manifest.

## Release contents

1. Ten new manual JSON curves, their hash/QC manifests, and the aggregate
   `manual/release_manifest.json` generated only by a complete verifier pass.
2. A 13-scroll index: ten bundled curves plus three external credited curves.
3. Screenshot hashes and QC metadata for every new curve. Include the CT-derived images themselves
   only with written redistribution permission or through an organizer-approved channel.
4. The reproducible slice-fetch, schema, and QC code needed to inspect the work, excluding local
   third-party reference files and caches.
5. A short limitations statement: these are fit-ready human approximations, not exact ground truth;
   the automatic seeds are only initialization; no Kaggle hidden-test or letter-reading claim.
6. After the external release is complete, a minimal Villa community-projects link PR for
   discoverability. Do not propose the annotation/QC apparatus as an in-tree analytics module;
   Paul explicitly redirected a comparable read-only audit to this link-only path in Villa #1408.

## Licence and attribution gates

- Add an explicit permissive software licence before public release. Confirm the submitter's exact
  legal-name spelling before creating its copyright notice.
- Select and state a data licence for the ten newly produced curve JSONs. Do not silently assume a
  software licence covers third-party or derived data.
- The official data-server terms forbid redistributing source data without written approval. A
  curve release must not include CT chunks/slices/caches; treat CT-derived screenshots separately
  as above. The approver accepts an explicit curve-data licence but does not make the legal choice
  for the user.
- Credit Sean Johnson (`@Bruniss`) and the 2026-08-08 `#general` source for the three prior curves;
  credit Villa for the schema, Khartes for the editor, and the Vesuvius Challenge for the CT data.
- If the public release is intended to bundle Sean's files, obtain and retain explicit permission
  plus the licence terms first. Otherwise keep them external-only.
- Confirm that every external-only row has a durable public source. If it does not, ask the user
  to obtain a stable link or redistribution permission before claiming a complete downloadable set.

## Submission wording boundary

Lead with: human-curated curves completing the previously missing coverage, a clear 13-scroll
index, standard Villa JSON, fresh-project reimport checks, full-z screenshots, and immediate Spiral
fit usability. Call it a complete downloadable 13-curve set only if all 13 newly drawn curves are
bundled, or the three external rows have durable public links/authorized copies. Say that
maintainers publicly identified the task as high-value. Do not call any cash amount guaranteed:
the official terms guarantee only one best-of-month $20,000 award and make all judging
discretionary.
