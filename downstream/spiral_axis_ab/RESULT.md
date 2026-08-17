# PHerc1218 production axis A/B result

## Outcome

The public manual PHerc1218 umbilicus is **not an admissible improvement** to
the stitched-pack baseline in this frozen production Spiral test. Do not
replace the pack axis on the strength of this experiment.

This is deliberately narrower than saying the baseline is anatomically true or
globally superior. The manual arm failed the preregistered run-health gate, the
blind CT review favored baseline on three of seven planes and tied four, and
the intrinsic comparison changed direction when the evaluation axis changed.
The operational decision is therefore **no replacement**; anatomical
superiority remains inconclusive.

## Frozen evidence

Both arms ran 30,000 optimizer steps with seed 1 on full-resolution
`z=[5220,6020)`, exactly three intersecting patches, the same RTX 3090 and the
same config SHA-256 `0a4838fd...21eaa`. The prepared datasets retained the
same non-axis manifest SHA-256 `57e52ab7...229825` and differed only in
`umbilicus.json`.

| Evidence | Baseline pack axis | Manual axis |
|---|---:|---:|
| Process / exactly 3 patches | pass | pass |
| Relative-PCL points (minimum 94%) | **94.922%** | **91.562% — fail** |
| Same-winding points (minimum 91%) | **91.237%** | **85.567% — fail** |
| L1 median radial gaps at z=5420/5620/5820 | 9.925 / 9.976 / 10.306 | 10.342 / 10.327 / 9.894 |
| Blind exact-CT preferences | **3** | **0** |
| Blind ties | 4 | 4 |
| Own-axis intrinsic violated bins | 6 / 72,315 (0.0083%) | 13 / 77,457 (0.0168%) |
| Own-axis collapsed bins | 11 / 72,315 (0.0152%) | 18 / 77,457 (0.0232%) |

The blind mapping was A=baseline and B=manual. The seven choices were locked
before unblinding: ties at z=5264, 5536, 5664 and 5952; baseline preferences at
z=5408, 5792 and 5872. The review describes gross contour continuity and
fold/bundle failures, not ground-truth accuracy.

The apparent intrinsic direction is not robust. In the baseline-axis frame,
baseline/manual violated-bin fractions were 0.0083%/0.8670%; in the manual-axis
frame they were 0.6575%/0.0168%. This decisive flip is why the own-axis numbers
above are not promoted into an anatomical winner claim. Axis-free valid-vertex
and valid-quad fractions were also nearly equal.

Constraint satisfaction remains a circular run-health check because the pack
axis, seed patches and PCLs share a stitched-label source. It is used here to
enforce the frozen admission rule, never as independent truth.

## Reproduce and audit

Machine-readable metrics, source pins, tree hashes and compact artifact hashes
are in [`result.json`](result.json). Generated meshes, exact-CT images and the
private blind key remain under ignored `work/production-v1/`; CT-derived images
are not committed.

```powershell
python downstream/spiral_axis_ab/run_axis_ab.py run `
  --work downstream/spiral_axis_ab/work/production-v1 `
  --villa-dir ..\_worktrees\villa-axis-ab-current `
  --python ..\_envs\spiral-axis-ab-clean\python.exe `
  --phase full --steps 30000

python downstream/spiral_axis_ab/evaluate_axis_ab.py `
  --baseline-run downstream/spiral_axis_ab/work/production-v1/outputs/full/baseline `
  --manual-run downstream/spiral_axis_ab/work/production-v1/outputs/full/manual `
  --baseline-umbilicus downstream/spiral_axis_ab/work/production-v1/datasets/baseline/umbilicus.json `
  --manual-umbilicus downstream/spiral_axis_ab/work/production-v1/datasets/manual/umbilicus.json `
  --out downstream/spiral_axis_ab/work/production-v1/evaluation-v1 --ct-level 1
```

The first interrupted production attempt is excluded. `production-v1` was
prepared afresh and independently reverified against the same hashes. During
its baseline arm, the process was suspended in memory once after step 6,646 at
the user's request and resumed at step 6,672; there was no checkpoint reload,
restart or input/config change. The recorded wall time includes that pause.
The manual arm ran uninterrupted.

The exact-CT package and both-axis intrinsic analysis were completed even
though the manual arm failed admission. An official flattening was not run and
cannot be inferred from these axial overlays. Sixteen focused Python tests
passed after completion.
