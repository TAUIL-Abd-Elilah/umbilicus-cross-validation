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
was redrawn manually in Khartes on a blank fragment. Neither automatic
initializer supplied its control set.

The proposed public diff includes the approved curve and its hash-bound QC
manifest. The byte-identical working candidate and reproducible QC tooling are
retained locally for the complete release. It intentionally excludes CT slices,
screenshots, caches, Khartes projects, and third-party reference files.

### PHerc1203 result

- 40 canonical integer `X,Y,Z` controls, strictly increasing from z=1500 to
  z=17775.
- Exact CT stream:
  `PHerc1203/volumes/20250820131727-9.362um-1.2m-113keV-masked.zarr`, level 0,
  9.362 micrometre voxels.
- Human reviewer: Abd Elilah.
- Curve-data licence: CC-BY-4.0.
- Approved curve SHA-256:
  `e58d635e5d4830788e6685f19d0ada10e4ff2f8a9f608dbfa47070473ea1bc27`.

### Validation

- Fresh Khartes project reimport: 40/40 controls match exactly, with zero
  mismatches.
- All 40 controls were placed and reviewed in the editing project; selected
  transitions and both endpoints were rechecked after the fresh reimport.
- Endpoint review found the compact core exiting through a damaged notch near
  z=17800. Later inspected slices at z=17900, 17998, and 18435 contain no
  discrete whorl, so the curve intentionally ends at the last supported control
  at z=17775 and makes no claim beyond it.
- Eight local evidence views decode correctly and are hash-bound by the QC
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

- [x] PHerc1203 blank-fragment redraw and exact fresh-project reimport
- [x] PHerc1203 useful-range/endpoint review, approval manifest, and Villa-loader check
- [x] Private CT-derived artifacts excluded from the proposed public diff
- [ ] Remaining nine manual curves approved
- [ ] Ten-scroll aggregate verifier and release manifest pass
- [ ] Final attribution, software licence, and public artifact links completed
- [ ] Draft wording refreshed against the final 10/10 facts
