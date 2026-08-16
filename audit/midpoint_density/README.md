# Adaptive midpoint-density audit

This audit tests the assumption that a roughly 30-control umbilicus can be
linearly interpolated between controls. It does **not** test absolute anatomical
truth.

Every one of 149 adjacent-control intervals across five viable curves was
screened on exact CT. Suspect intervals were rerendered at higher resolution and
then in candidate-following XZ/YZ sections. PHerc1203 is excluded because its
separate full-curve audit already withdrew it from recommended use.

| Curve | Intervals | Keep linear | Add control | Unresolved |
|---|---:|---:|---:|---:|
| PHerc0191 | 29 | 25 | 2 | 2 |
| PHerc0257 | 30 | 29 | 1 | 0 |
| PHerc0358 v2 candidate | 30 | 30 | 0 | 0 |
| PHerc0800 | 30 | 20 | 7 | 3 |
| PHerc0813 | 30 | 27 | 0 | 3 |
| **Total** | **149** | **131** | **10** | **8** |

The decision meanings are deliberately conservative:

- `keep_linear`: no visible interpolation break remained after the recorded
  screens; this is not proof that the whole curve is anatomically correct.
- `add_control`: linear interpolation appears inadequate, but no replacement
  coordinate has been selected. Place it independently in an interactive viewer,
  then rerender both neighboring intervals.
- `unresolved`: do not edit from the current evidence.

The complete partition and evidence paths are in
[`assisted_screening_summary.json`](assisted_screening_summary.json). The review
is AI-assisted visual triage, not experienced-user acceptance. CT panels remain
local; the public JSONs bind the curve hashes, source stream, parameters, segment
numbers, valid Zarr fill chunks, and failed-fetch count.

## Reproduce

```powershell
# Fast axial screen of every midpoint.
python audit_midpoint_density.py --scroll PHerc0813 --level 3

# Higher-resolution escalation of selected one-based intervals.
python audit_midpoint_density.py --scroll PHerc0813 --level 2 `
  --segment 1 --segment 10 --segment 11

# Candidate-following XZ/YZ continuity review.
python render_midpoint_orthogonals.py --scroll PHerc0813 --level 3 `
  --segment 1 --segment 10 --segment 11

# Verify the partition and its curve-bound receipt metadata.
python verify_midpoint_screening.py
```

The renderers accept a Zarr 404 only after validating `fill_value=0` from that
pyramid level's metadata. Other fetch failures abort. Empty source panels and
corrupt cache tiles also abort.
