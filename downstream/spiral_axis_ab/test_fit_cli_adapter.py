from __future__ import annotations

import ast
from pathlib import Path
import unittest


class FitCliAdapterTests(unittest.TestCase):
    def test_adapter_stays_path_resolution_only(self) -> None:
        source = Path(__file__).with_name("fit_cli_adapter.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertNotIn("torch", imported)
        self.assertNotIn("numpy", imported)
        self.assertIn("resolve_dataset_root", source)
        self.assertIn("conventional_input_paths", source)
        self.assertIn("runpy.run_path", source)


if __name__ == "__main__":
    unittest.main()
