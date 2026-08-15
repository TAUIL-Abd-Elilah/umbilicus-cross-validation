# khartes handoff - 10 scrolls needing a manual umbilicus

Two starting curves ship per scroll. Load whichever is closer and correct it:

  seeds/<scroll>_umbilicus_seed.json        body centroid, 289-382 voxels on the references
  seeds/<scroll>_umbilicus_estimated.json   lasagna normals, 152-409 voxels - better on 2 of 3

Neither is a finished umbilicus. The estimate beats the seed on PHerc0125 (-48%) and
PHerc0211 (-30%) but is worse on PHerc0826 (+7%), so check both before starting a scroll.
Points with score=0 are QC-flagged (the centroid jumped) - place those from scratch.

Use the tested Khartes branch `codex/manual-control-export-fix` at current local head
`060816f9d0cff5a452365090e16aef4eb2507137` (canonical-control commit
`9e6b6bb31bfed71760ef89bc60e9612404e3ca97`; ambiguous-export guard `060816f`).
Target 24-32 canonical manual controls;
the supplied lasagna estimates have 40 and may remain at 40 after correction rather than being
thinned just to hit a number.
That branch keeps those controls authoritative through interpolation, undo, copy, save/reopen,
and standard Villa XYZ JSON import/export. It now refuses an umbilicus export unless exactly one
fragment is active, instead of silently using the first active fragment. The existing hand-drawn
curves are self-consistent to 32-63 voxels median, which is the bar.

| # | scroll | coarse body bracket | flagged seed controls | exact flagged z |
|---|---|---|---|---|
| 1 | PHerc0191 | 960 - 18976 | 2/32 | 1320, 18616 |
| 2 | PHerc0257 | 960 - 18368 | 4/32 | 1308, 1847, 2386, 18020 |
| 3 | PHerc0268 | 384 - 14816 | 11/32 | 673, 1120, 1566, 2907, 11846, 12293, 12740, 13187, 13634, 14080, 14527 |
| 4 | PHerc0358 | 384 - 14720 | 4/32 | 671, 1559, 13989, 14433 |
| 5 | PHerc0800 | 0 - 24288 | 2/32 | 21546, 23802 |
| 6 | PHerc0813 | 1728 - 16992 | 1/32 | 16687 |
| 7 | PHerc1203 | 960 - 18976 | 0/32 | none |
| 8 | PHerc1218 | 0 - 23232 | 3/32 | 465, 22048, 22767 |
| 9 | PHerc1447 | 0 - 24288 | 4/32 | 486, 1238, 1990, 23802 |
| 10 | PHerc1545 | 1088 - 20960 | 1/32 | 1485 |

Start with PHerc1203 (0 flagged). Leave PHerc0268 (11 flagged) for last.

Exact public streams for the later queue are:

| scroll | OME/Zarr stream |
|---|---|
| PHerc0191 | `https://vesuvius-challenge-open-data.s3.amazonaws.com/PHerc0191/volumes/20250821151635-9.362um-1.2m-113keV-masked.zarr` |
| PHerc0257 | `https://vesuvius-challenge-open-data.s3.amazonaws.com/PHerc0257/volumes/20250821151750-9.362um-1.2m-113keV-masked.zarr` |
| PHerc0268 | `https://vesuvius-challenge-open-data.s3.amazonaws.com/PHerc0268/volumes/20251110183117-8.640um-1.2m-116keV-masked.zarr` |
| PHerc0358 | `https://vesuvius-challenge-open-data.s3.amazonaws.com/PHerc0358/volumes/20250821151737-9.362um-1.2m-113keV-masked.zarr` |
| PHerc0800 | `https://vesuvius-challenge-open-data.s3.amazonaws.com/PHerc0800/volumes/20250521135224-8.640um-1.2m-116keV-masked.zarr` |
| PHerc0813 | `https://vesuvius-challenge-open-data.s3.amazonaws.com/PHerc0813/volumes/20250821151723-9.362um-1.2m-113keV-masked.zarr` |
| PHerc1203 | `https://vesuvius-challenge-open-data.s3.amazonaws.com/PHerc1203/volumes/20250820131727-9.362um-1.2m-113keV-masked.zarr` |
| PHerc1218 | `https://vesuvius-challenge-open-data.s3.amazonaws.com/PHerc1218/volumes/20250521120456-8.640um-1.2m-116keV-masked.zarr` |
| PHerc1447 | `https://vesuvius-challenge-open-data.s3.amazonaws.com/PHerc1447/volumes/20250521151220-8.640um-1.2m-116keV-masked.zarr` |
| PHerc1545 | `https://vesuvius-challenge-open-data.s3.amazonaws.com/PHerc1545/volumes/20250821151648-9.362um-1.2m-113keV-masked.zarr` |

## First operator pass: PHerc1203

The isolated operator environment is installed at `_tools/khartes-exp/.venv`.
On 2026-08-12 it passed all 5 canonical-control/import/export tests, a headless main-window
startup, and a real metadata connection to the PHerc1203 public OME/Zarr stream (6 levels,
shape `18977 x 6844 x 6844`, `uint8`). Do not launch it while other memory-heavy training is
using the machine.

Launch only in a user-controlled desktop session:

```powershell
Set-Location 'D:\Competition\Vesuvius progress prizes\_tools\khartes-exp'
& '.\.venv\Scripts\python.exe' '.\khartes.py'
```

Then perform this exact pass:

1. `File > New Project...`; create a fresh project named `PHerc1203-manual` outside the source
   tree, for example under
   `D:\Competition\Vesuvius progress prizes\_operator_projects\PHerc1203-manual`.
2. `File > Attach OME/Zarr data stream...`; paste this verified public URL, set volume name
   `PHerc1203`, leave `Data is from vc_layers` unchecked, and click `Connect`:

   `https://vesuvius-challenge-open-data.s3.amazonaws.com/PHerc1203/volumes/20250820131727-9.362um-1.2m-113keV-masked.zarr`
3. Import both candidate JSON files as separate umbilicus fragments using
   `File > Import Umbilicus files...` and canonical `X,Y,Z`:
   `D:\Competition\Vesuvius progress prizes\umbilicus13\seeds\PHerc1203_umbilicus_seed.json`
   and
   `D:\Competition\Vesuvius progress prizes\umbilicus13\seeds\PHerc1203_umbilicus_estimated.json`.
4. Compare them through z, retain the closer starting fragment, and deactivate the other.
   In the `Fragments` tab make only the retained curve active and visible. Work in normal mode:
   hover a red control until it turns cyan, then drag it in a Data Slice; arrow keys provide
   fine adjustment. `Shift`+left-click adds a control, `Delete`/`Backspace` removes the cyan
   control, and `Ctrl+Z` restores the last edit on this repaired branch. Correct the
   **canonical controls**, not the interpolated display samples. Use 24-32 controls with unique
   z coordinates (or keep all 40 if the lasagna estimate is the better base). Inspect the whole
   useful body range inside the coarse `960-18976` bracket and avoid relying on unchecked endpoint
   extrapolation. Save frequently with `Ctrl+S` (Khartes has no automatic backups). PHerc1203 has
   no score-0 seed points.
5. Make only the finished fragment active. The repaired branch now refuses to continue if any
   second fragment is active. Use `File > Export segment as mesh...`; Khartes
   recognizes an umbilicus and opens its dedicated exporter. Choose the default
   `.json (Villa control_points)` and `X,Y,Z`, exporting the working candidate to
   `D:\Competition\Vesuvius progress prizes\umbilicus13\manual\candidates\PHerc1203_umbilicus.candidate.json`.
   This is deliberately not the final release filename. The exporter refuses to overwrite.
6. Create a second fresh project, attach the same public stream, and reimport the exported JSON
   with `X,Y,Z`. Confirm all canonical controls and the interpolated track are unchanged, and
   inspect at least the start, middle, end, and every ambiguous transition. If it fails, move the
   rejected candidate aside under `manual/candidates/rejected/`, return to the editing project,
   and export a new candidate at the exact path above. Never promote a failed candidate.
7. Save at least start/middle/end screenshots under
   `umbilicus13/manual/screenshots/PHerc1203/`, with `PHerc1203` in every filename. Also retain each
   ambiguous transition. Keep the role and displayed z as filename tokens (for example
   `PHerc1203_start_z0960.png`); the three required views must be distinct and ordered in z, and
   evidence must be a real PNG/JPEG at least 256x256. CT-derived screenshots stay local or in an organizer-approved channel;
   do not commit them publicly without written redistribution permission.
8. Only after the fresh-project/full-z check, run `approve_manual_curve.py`. It rejects an exact
   untouched seed/estimate, wrong stream/range/schema, out-of-volume controls, insufficient useful-z
   coverage, invalid/misnamed screenshots, missing human QC, and overwrite attempts. It creates
   both the final JSON and a hash-bound v2 QC manifest. The
   user must first confirm the reviewer spelling, timestamp, and curve-data licence. Example:

   ```powershell
   Set-Location 'D:\Competition\Vesuvius progress prizes\umbilicus13'
   python .\approve_manual_curve.py --scroll PHerc1203 `
     --reviewer '<CONFIRMED LEGAL NAME>' --qc-time '<ISO-8601 WITH TIMEZONE>' `
     --ct-url 'https://vesuvius-challenge-open-data.s3.amazonaws.com/PHerc1203/volumes/20250820131727-9.362um-1.2m-113keV-masked.zarr' `
     --data-license '<CC-BY-4.0|CC-BY-NC-4.0|CC0-1.0>' `
     --screenshot '.\manual\screenshots\PHerc1203\PHerc1203_start_z0960.png' `
     --screenshot '.\manual\screenshots\PHerc1203\PHerc1203_middle_z9968.png' `
     --screenshot '.\manual\screenshots\PHerc1203\PHerc1203_end_z18976.png' --qc-checked
   ```

   Successful approval writes `manual/PHerc1203_umbilicus.json` and
   `manual/manifests/PHerc1203_qc.json`. A curve without its matching manifest is not releasable.

Neither automatic input may be published as a finished umbilicus. Repeat this workflow through
the eligible queue only after PHerc1203 passes the reopen/visual check; leave PHerc0268 for last.
Record each completed curve and screenshot set against `../PUBLICATION_CHECKLIST.md`.

After all ten curves pass, run `python .\verify_manual_release.py` from `umbilicus13`. It must
report a complete ten-curve pass through Villa's real loader before publication. Then rerun with
`--write-manifest` exactly once to install `manual/release_manifest.json`; it refuses overwrite.

## Protected validation boundary

PHerc0826 is not part of this operator pass. Do not open, render, import, score, or inspect its
imagery or reference material. Current strategy reserves that target; begin with PHerc1203 and
continue only through the eligible queue above. Claude's prior agent-blind sequential attempt is
already spent; if a future human protocol uses PHerc0826, describe it only as the manual
workflow's blind measurement, not the project's first blind measurement.

Publication closure may later require the **user**, not this agent, to redraw PHerc0125,
PHerc0211, and PHerc0826 so the released 13-curve set has one clear owner/licence. Do that only
after the ten-scroll queue passes QC. Never copy the local third-party reference files into the
manual output directory.
