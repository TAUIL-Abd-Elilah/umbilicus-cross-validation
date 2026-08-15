# Manual QC manifests

`approve_manual_curve.py` writes one no-overwrite v2 manifest here for each approved
curve. It binds the curve, candidate, decoded screenshot roles/dimensions/hashes,
volume bounds, automatic initializers, CT stream, reviewer, and data licence. A JSON
curve without its matching manifest is not release-ready.
