# Draft PR: PHerc1203 manual umbilicus checkpoint

Status: **draft only; do not publish or request review yet**. This is a 1/10
progress checkpoint for the future external curve release, not the complete
ten-scroll release and not an upstream Villa feature PR.

## Proposed title

`[Draft checkpoint] PHerc1203: first human-reviewed umbilicus (1/10)`

## Proposed body

### Summary

This checkpoints the first of ten missing human-curated prize-scroll umbilici:
PHerc1203. The curve uses Villa's existing `control_points` JSON contract and
was corrected manually in Khartes from an automatic starting curve.

The proposed public diff includes the approved curve and its hash-bound QC
manifest. The byte-identical working candidate and reproducible QC tooling are
retained locally for the complete release. It intentionally excludes CT slices,
screenshots, caches, Khartes projects, and third-party reference files.

### PHerc1203 result

- 40 canonical integer `X,Y,Z` controls, strictly increasing from z=1500 to
  z=18435.
- Exact CT stream:
  `PHerc1203/volumes/20250820131727-9.362um-1.2m-113keV-masked.zarr`, level 0,
  9.362 micrometre voxels.
- Human reviewer: Abd Elilah.
- Curve-data licence: CC-BY-4.0.
- Approved curve SHA-256:
  `8c2ba6379a8605c84daf58eda6eb6c7245a666b9987178c170d4dfce57862490`.

### Validation

- Fresh Khartes project reimport: 40/40 controls match exactly.
- Dense full-z review: 362/362 samples checked at 47-48-slice spacing.
- Ambiguous z=17610-17993 transition rechecked in three orthogonal views.
- Seven local evidence views decode correctly and are hash-bound by the QC
  manifest; the images are not redistributed.
- Official Villa `json_umbilicus_z_to_yx` loader: pass.
- Single-scroll release-contract validation: pass.
- Approval/verifier unit suite: 13 tests pass.

### Scope and limitations

This curve is a fit-ready human approximation, not exact ground truth, and it
makes no surface-quality, unrolling, hidden-test, letter-reading, or prize claim.
The aggregate verifier must remain incomplete until all ten new curves pass the
same approval contract. Keep this PR in draft and do not present it as a release.

CT-derived evidence remains local because the data-server terms do not permit
redistributing source scans or derived screenshots without written permission.
The manifest publishes hashes and QC metadata only.

### Completion checklist

- [x] PHerc1203 human correction and fresh-project reimport
- [x] PHerc1203 dense review, approval manifest, and Villa-loader check
- [x] Private CT-derived artifacts excluded from the proposed public diff
- [ ] Remaining nine manual curves approved
- [ ] Ten-scroll aggregate verifier and release manifest pass
- [ ] Final attribution, software licence, and public artifact links completed
- [ ] Draft wording refreshed against the final 10/10 facts
