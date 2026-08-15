# khartes handoff - 10 scrolls needing a manual umbilicus

Two automatic curves ship per scroll as visual guides:

  seeds/<scroll>_umbilicus_seed.json        body centroid, 289-382 voxels on the references
  seeds/<scroll>_umbilicus_estimated.json   lasagna normals, 152-409 voxels - better on 2 of 3

Neither is a finished umbilicus and neither should supply the output controls by default. Draw the
publishable curve on a blank fragment while using the guides only for orientation. The estimate
beats the seed on PHerc0125 (-48%) and
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

PHerc1203 and PHerc0191 are complete and locally approved (2/10). Continue with PHerc0257; leave PHerc0268
(11 flagged) for last.

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

Completed on 2026-08-15 as a 40-control blank-fragment redraw spanning z=1500-17775. The exact
fresh-project reimport had zero mismatches, all eight declared evidence views passed validation,
and the candidate passed the real Villa loader. Later inspected slices show the compact core
exiting through damage, so no extrapolation beyond z=17775 is claimed.

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

## Standing pass for the remaining eight

Steps 1-3 below are pure setup and are now pre-built. `make_operator_project.py` writes the
Khartes project directly — stream attached, both guides imported and switched off, blank output
fragment active, view parked on the first guide control — so the session starts on the drawing.

All projects for the original nine-scroll queue already exist in `_operator_projects\<scroll>-manual.khprj` and were each
loaded through Khartes' own `ProjectView.open` against the live stream on 2026-08-15: every one
reports a valid 6-level volume at the shape recorded in `scrolls.py`, both guides parsed, and a
0-control active output fragment. To rebuild one (for example after a discarded attempt):

```powershell
Set-Location 'D:\Competition\Vesuvius progress prizes\umbilicus13'
python .\make_operator_project.py PHerc0257 --force
```

Then perform this exact pass, using PHerc0257 as the live example:

1. `File > Open Project...` on
   `D:\Competition\Vesuvius progress prizes\_operator_projects\PHerc0257-manual.khprj`.
   Do not use `File > New Project...` unless a project must be rebuilt from scratch.
2. Confirm the attached stream is the expected one for the scroll (the table above), and that the
   volume loads. Nothing needs to be pasted or connected by hand.
3. The two automatic guides are already imported as `<scroll>_guide_seed` and
   `<scroll>_guide_estimated`, both hidden and inactive, and `<scroll>_manual` is the active blank
   output fragment. Neither guide can reach the export unless it is deliberately activated.
4. Show each guide briefly to compare them through z, then hide them again and draw on the blank
   output fragment. Keep only the blank output active while editing; show a guide temporarily only
   when orientation is useful.
   Work in normal mode:
   hover a red control until it turns cyan, then drag it in a Data Slice; arrow keys provide
   fine adjustment. `Shift`+left-click adds a control, `Delete`/`Backspace` removes the cyan
   control, and `Ctrl+Z` restores the last edit on this repaired branch. Correct the
   **canonical controls**, not the interpolated display samples. Use 24-32 controls with unique
   z coordinates (40 is also acceptable when the anatomy needs denser coverage). Inspect the whole
   useful body range inside that scroll's coarse bracket from the table above (PHerc0257:
   `960-18368`) and avoid relying on unchecked endpoint extrapolation. Save frequently with
   `Ctrl+S` (Khartes has no automatic backups). Place the scroll's flagged score-0 z values from
   scratch rather than nudging a guide (PHerc0257: `1308`, `1847`, `2386`, `18020`).
5. Make only the finished fragment active — hide and deactivate both guides. The repaired branch
   refuses to continue if any second fragment is active. Use `File > Export segment as mesh...`;
   Khartes recognizes an umbilicus and opens its dedicated exporter. Choose the default
   `.json (Villa control_points)` and `X,Y,Z`, exporting the working candidate to
   `D:\Competition\Vesuvius progress prizes\umbilicus13\manual\candidates\PHerc0257_umbilicus.candidate.json`.
   This is deliberately not the final release filename. The exporter refuses to overwrite.
6. Build the reimport QC project from that candidate and open it. It attaches the same public
   stream and loads the candidate as a single inactive fragment, so the check cannot silently
   become an edit:

   ```powershell
   Set-Location 'D:\Competition\Vesuvius progress prizes\umbilicus13'
   python .\make_operator_project.py PHerc0257 --candidate .\manual\candidates\PHerc0257_umbilicus.candidate.json
   ```

   Confirm all canonical controls and the interpolated track are unchanged, and
   inspect at least the start, middle, end, and every ambiguous transition. If it fails, move the
   rejected candidate aside under `manual/candidates/rejected/`, return to the editing project,
   and export a new candidate at the exact path above. Never promote a failed candidate.
7. Save at least start/middle/end screenshots under
   `umbilicus13/manual/screenshots/PHerc0257/`, with `PHerc0257` in every filename. Also retain each
   ambiguous transition. Keep the role and displayed z as filename tokens (for example
   `PHerc0257_start_z<Z>.png`); the three required views must be distinct and ordered in z, and
   evidence must be a real PNG/JPEG at least 256x256. CT-derived screenshots stay local or in an organizer-approved channel;
   do not commit them publicly without written redistribution permission.
8. Only after the fresh-project/full-z check, run `approve_manual_curve.py`. It rejects an exact
   untouched seed/estimate, wrong stream/range/schema, out-of-volume controls, insufficient useful-z
   coverage, invalid/misnamed screenshots, missing human QC, and overwrite attempts. It creates
   both the final JSON and a hash-bound v2 QC manifest. The
   user must first confirm the reviewer spelling, timestamp, and curve-data licence. Example:

   ```powershell
   Set-Location 'D:\Competition\Vesuvius progress prizes\umbilicus13'
   python .\approve_manual_curve.py --scroll PHerc0257 `
     --reviewer '<CONFIRMED LEGAL NAME>' --qc-time '<ISO-8601 WITH TIMEZONE>' `
     --ct-url 'https://vesuvius-challenge-open-data.s3.amazonaws.com/PHerc0257/volumes/20250821151750-9.362um-1.2m-113keV-masked.zarr' `
     --data-license 'CC-BY-4.0' `
     --screenshot '.\manual\screenshots\PHerc0257\PHerc0257_start_z<Z>.png' `
     --screenshot '.\manual\screenshots\PHerc0257\PHerc0257_middle_z<Z>.png' `
     --screenshot '.\manual\screenshots\PHerc0257\PHerc0257_end_z<Z>.png' --qc-checked
   ```

   PHerc1203 and PHerc0191 were approved as CC-BY-4.0; keep every curve on that same licence so the release has
   one coherent data licence, which `verify_manual_release.py` requires. Successful approval writes
   `manual/PHerc0257_umbilicus.json` and `manual/manifests/PHerc0257_qc.json`. A curve without its
   matching manifest is not releasable.

Neither automatic input may be published as a finished umbilicus. PHerc1203 and PHerc0191 have passed the
reopen/visual check; repeat this workflow through the remaining eligible queue and leave PHerc0268
for last.
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
