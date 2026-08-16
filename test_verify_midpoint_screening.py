import json
from pathlib import Path
import tempfile
import unittest

from verify_midpoint_screening import ScreeningError, verify_summary


class MidpointScreeningReceiptTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent
        self.summary = self.root / "audit" / "midpoint_density" / "assisted_screening_summary.json"

    def write_mutated_summary(self, mutate, directory: str) -> Path:
        data = json.loads(self.summary.read_text(encoding="utf-8"))
        mutate(data)
        path = Path(directory) / "summary.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_public_summary_has_complete_curve_bound_receipts(self):
        self.assertEqual(verify_summary(self.summary, self.root), (5, 149))

    def test_curve_hash_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_mutated_summary(
                lambda data: data["scrolls"]["PHerc0191"]["curve"].update(sha256="0" * 64),
                directory,
            )
            with self.assertRaisesRegex(ScreeningError, "curve hash mismatch"):
                verify_summary(path, self.root)

    def test_duplicate_decision_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            def mutate(data):
                data["scrolls"]["PHerc0191"]["keep_linear"].append(1)

            path = self.write_mutated_summary(mutate, directory)
            with self.assertRaisesRegex(ScreeningError, "sorted and unique"):
                verify_summary(path, self.root)

    def test_missing_orthogonal_coverage_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            def mutate(data):
                data["scrolls"]["PHerc0257"]["escalation_manifests"] = [
                    "audit/midpoint_density/PHerc0257_level2_segments_006-008-012-013-015-030.json"
                ]

            path = self.write_mutated_summary(mutate, directory)
            with self.assertRaisesRegex(ScreeningError, "orthogonal evidence"):
                verify_summary(path, self.root)


if __name__ == "__main__":
    unittest.main()
