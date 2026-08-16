# Downstream proxy comparison

This folder makes the exploratory downstream results reproducible. Neither
metric is ground truth:

- the neutral traced-arc fixture measures preservation of radial ordering on a
  fixed external trace;
- radial-anisotropy `q` measures local CT structure-tensor alignment and can
  prefer the wrong V-shaped cusp.

For this reason, results are reported with exact-CT overlays and continuity
review. Correlated slices are not assigned pooled p-values.

## Archived results

| Scroll | strict three-axis winding order (public / independent / auto) | q difference (independent − public) | wins |
|---|---:|---:|---:|
| PHerc0191 | .912 / .846 / .853 | +.03345 | 4/6 |
| PHerc0257 | — | +.00187 | 4/6 |
| PHerc0358 | .900 / .900 / .733 | −.00624 | 3/6 |
| PHerc0800 | — | −.03408 | 2/6 |
| PHerc0813 | — | −.06137 | 1/6 |
| PHerc1203 | .851 / .851 / .786 | −.04227 | 3/6 |

Pooled descriptive q difference: −0.01811; independent wins 17/36. The
public scorer was reproduced to numerical precision before substituting the
independent curves.

## Commands

```powershell
python audit/downstream/compare_order_fixtures.py `
  --output audit/downstream/reproduced_order.json

# Streams 36 fixed public CT slices; requires explicit network confirmation.
python audit/downstream/compare_axis_q.py `
  --protocol screen6 --confirm-network `
  --output audit/downstream/reproduced_axis_q.json

python audit/downstream/validate_receipts.py audit/downstream
```

To score a preregistered one-scroll correction candidate:

```powershell
python audit/downstream/compare_axis_q.py `
  --protocol screen6 --scrolls PHerc0358 --confirm-network --allow-source-drift `
  --curve-override audit/corrections/PHerc0358_umbilicus.v2.candidate.json `
  --output audit/corrections/PHerc0358_v2_axis_q.json
```

Pins: independent curve-producing commit `3a1d8aa`; public repository
`57e09a3`; Villa `94ba2159`. Full hashes are recorded inside each receipt.
