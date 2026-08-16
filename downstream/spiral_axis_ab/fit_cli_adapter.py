"""Run Villa's merged CLI with its existence-probing dataset resolver.

Current Villa main's headless CLI uses ``conventional_input_paths()``, which
intentionally returns conventional paths without checking whether optional
assets exist. The fitter then sees two nonexistent paths (tracks and shell) as
truthy and attempts to load ``outer_shell/meta.json`` even when every shell
loss is disabled. The interactive service already avoids this via
``resolve_dataset_root()``.

This tiny adapter swaps only that path-resolution function, reusing Villa's
own service resolver. Configuration, count scaling, fitting, metrics, and
export all remain in the unmodified pinned ``fit_spiral.py``.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import runpy
import sys


def main(argv: list[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    if not values:
        raise SystemExit("usage: fit_cli_adapter.py FIT_SPIRAL.py [CLI arguments]")
    fit_script = Path(values.pop(0)).resolve()
    if not fit_script.is_file():
        raise SystemExit(f"missing fit_spiral.py: {fit_script}")
    sys.path.insert(0, str(fit_script.parent))

    import fit_session  # pylint: disable=import-outside-toplevel

    conventional = fit_session.conventional_input_paths

    def resolved_input_paths(dataset_root, scroll_spec, **kwargs):
        original = conventional(dataset_root, scroll_spec, **kwargs)
        resolution = fit_session.resolve_dataset_root(dataset_root)
        if not resolution.ok:
            raise RuntimeError(
                "dataset resolution failed: "
                f"missing_required={resolution.missing_required}, "
                f"ambiguities={resolution.ambiguities}"
            )
        updates = {
            item.key: resolution.resolved.get(item.key, "")
            for item in fit_session.FIT_INPUT_CATALOG
            if item.kind != "pcl-set"
        }
        updates["pcls"] = tuple(
            fit_session.PclInputSpec.from_mapping(item)
            for item in resolution.pcl_inputs
        )
        return replace(original, **updates)

    fit_session.conventional_input_paths = resolved_input_paths
    sys.argv = [str(fit_script), *values]
    runpy.run_path(str(fit_script), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
