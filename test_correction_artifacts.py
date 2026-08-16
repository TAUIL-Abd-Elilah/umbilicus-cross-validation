import json
from pathlib import Path
import re
import unittest

from compare_independent_curves import load_curve, sha256


class CorrectionArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parent
        cls.source_path = cls.root / "manual" / "PHerc0358_umbilicus.json"
        cls.candidate_path = cls.root / "audit" / "corrections" / "PHerc0358_umbilicus.v2.candidate.json"
        cls.prereg_path = cls.root / "audit" / "corrections" / "PHerc0358_z5500_preregistration.json"

    def test_candidate_changes_only_preregistered_control(self):
        source = json.loads(self.source_path.read_text(encoding="utf-8"))["control_points"]
        candidate = json.loads(self.candidate_path.read_text(encoding="utf-8"))["control_points"]
        self.assertEqual(len(source), len(candidate))
        changes = [(before, after) for before, after in zip(source, candidate) if before != after]
        self.assertEqual(len(changes), 1)
        before, after = changes[0]
        self.assertEqual((before["x"], before["y"], before["z"]), (4500, 4650, 5500))
        self.assertEqual((after["x"], after["y"], after["z"]), (4162, 3821, 5500))

    def test_preregistration_and_receipts_bind_current_hashes(self):
        source_hash = sha256(self.source_path)
        candidate_hash = sha256(self.candidate_path)
        prereg = json.loads(self.prereg_path.read_text(encoding="utf-8"))
        comparison = json.loads(
            (self.root / "audit" / "corrections" / "PHerc0358_v2_comparison.json").read_text(encoding="utf-8")
        )
        validation = json.loads(
            (self.root / "audit" / "corrections" / "PHerc0358_v2_validation.json").read_text(encoding="utf-8")
        )
        self.assertEqual(prereg["source_curve"]["sha256"], source_hash)
        self.assertEqual(comparison["scrolls"][0]["ours"]["sha256"], candidate_hash)
        self.assertEqual(validation["candidate"]["sha256"], candidate_hash)
        self.assertTrue(validation["result"]["passed"])
        self.assertEqual(validation["result"]["controls_reproduced"], 31)

    def test_candidate_schema_loads_and_has_strictly_increasing_z(self):
        points = load_curve(self.candidate_path)
        self.assertEqual(points.shape, (31, 3))
        self.assertTrue(bool((points[1:, 2] > points[:-1, 2]).all()))

    def test_public_receipts_do_not_expose_machine_local_paths(self):
        receipts = (
            self.root / "audit" / "corrections" / "PHerc0358_v2_axis_q.json",
            self.root / "audit" / "downstream" / "results_order_fixtures_20260816.json",
        )
        for receipt in receipts:
            data = json.loads(receipt.read_text(encoding="utf-8"))
            pending = [data]
            while pending:
                value = pending.pop()
                if isinstance(value, dict):
                    pending.extend(value.values())
                elif isinstance(value, list):
                    pending.extend(value)
                elif isinstance(value, str) and ("/" in value or "\\" in value):
                    self.assertIsNone(
                        re.match(r"^[A-Za-z]:[\\/]", value),
                        f"machine-local path in {receipt}: {value}",
                    )
                    self.assertNotIn("\\", value, f"non-portable path in {receipt}: {value}")


if __name__ == "__main__":
    unittest.main()
