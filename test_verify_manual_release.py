from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from PIL import Image

import approve_manual_curve as approval
from scrolls import SCROLLS
import verify_manual_release as release


SOURCE_ROOT = Path(__file__).resolve().parent
VILLA_LOADER = (
    SOURCE_ROOT.parent
    / "villa"
    / "volume-cartographer"
    / "scripts"
    / "spiral"
    / "umbilicus.py"
)


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def points(scroll: str, offset: int, count: int = 24):
    bracket_min, bracket_max = approval.ELIGIBLE[scroll]["bracket"]
    z_min = bracket_min + 1
    z_max = bracket_max - 1
    _, y_size, x_size = SCROLLS[scroll]["shape"]
    return [
        {
            "x": x_size // 2 + offset + index,
            "y": y_size // 2 + index,
            "z": round(z_min + index * (z_max - z_min) / (count - 1)),
            "score": 100,
        }
        for index in range(count)
    ]


class VerifyManualReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        shutil.copyfile(SOURCE_ROOT / "approve_manual_curve.py", self.root / "approve_manual_curve.py")
        shutil.copyfile(SOURCE_ROOT / "verify_manual_release.py", self.root / "verify_manual_release.py")

        for scroll in sorted(approval.ELIGIBLE):
            write_json(
                self.root / "seeds" / f"{scroll}_umbilicus_seed.json",
                {"control_points": points(scroll, 0)},
            )
            write_json(
                self.root / "seeds" / f"{scroll}_umbilicus_estimated.json",
                {"control_points": points(scroll, 80)},
            )
            candidate = (
                self.root
                / "manual"
                / "candidates"
                / f"{scroll}_umbilicus.candidate.json"
            )
            write_json(candidate, {"control_points": points(scroll, 30)})

            screenshots = []
            for role, z_value, color in (
                ("start", 1, (30, 40, 50)),
                ("middle", SCROLLS[scroll]["shape"][0] // 2, (40, 50, 60)),
                ("end", SCROLLS[scroll]["shape"][0] - 1, (50, 60, 70)),
            ):
                path = (
                    self.root
                    / "manual"
                    / "screenshots"
                    / scroll
                    / f"{scroll}_{role}_z{z_value}.png"
                )
                path.parent.mkdir(parents=True, exist_ok=True)
                Image.new("RGB", (320, 256), color=color).save(path)
                screenshots.append(path)

            approval.approve(
                root=self.root,
                scroll=scroll,
                candidate=candidate,
                reviewer="Human Reviewer",
                qc_time="2026-08-12T20:00:00+00:00",
                ct_url=approval.expected_ct_url(scroll),
                data_license="CC-BY-4.0",
                screenshots=screenshots,
                qc_checked=True,
            )

    def tearDown(self):
        self.temp.cleanup()

    def verify(self):
        return release.verify_release(self.root, VILLA_LOADER)

    def test_verifies_all_ten_with_real_villa_loader(self):
        manifest = self.verify()
        self.assertEqual(manifest["format"], release.RELEASE_FORMAT)
        self.assertEqual(manifest["curve_count"], 10)
        self.assertEqual(manifest["data_license"], "CC-BY-4.0")
        self.assertEqual(manifest["scrolls"], sorted(approval.ELIGIBLE))
        self.assertEqual(len(manifest["release_content_sha256"]), 64)
        self.assertTrue(
            all(entry["approved_curve"]["control_count"] == 24 for entry in manifest["entries"])
        )

    def test_writes_only_complete_no_overwrite_aggregate_manifest(self):
        manifest = self.verify()
        output = release.write_manifest(self.root, manifest)
        written = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(written["release_content_sha256"], manifest["release_content_sha256"])
        self.assertEqual(self.verify(), written)
        with self.assertRaisesRegex(release.ReleaseError, "refusing to overwrite"):
            release.write_manifest(self.root, manifest)

        written["data_license"] = "CC0-1.0"
        write_json(output, written)
        with self.assertRaisesRegex(release.ReleaseError, "stale or tampered"):
            self.verify()

    def test_rejects_tampered_curve_or_screenshot(self):
        scroll = sorted(approval.ELIGIBLE)[0]
        final = self.root / "manual" / f"{scroll}_umbilicus.json"
        final.write_bytes(final.read_bytes() + b" ")
        with self.assertRaisesRegex(release.ReleaseError, "no longer matches"):
            self.verify()

        final.write_bytes(
            (self.root / "manual" / "candidates" / f"{scroll}_umbilicus.candidate.json").read_bytes()
        )
        screenshot = self.root / "manual" / "screenshots" / scroll / f"{scroll}_start_z1.png"
        Image.new("RGB", (320, 256), color=(200, 10, 10)).save(screenshot)
        with self.assertRaisesRegex(release.ReleaseError, "screenshot evidence changed"):
            self.verify()

    def test_rejects_mixed_licences_and_changed_tools(self):
        scroll = sorted(approval.ELIGIBLE)[0]
        manifest_path = self.root / "manual" / "manifests" / f"{scroll}_qc.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["data_license"] = "CC0-1.0"
        write_json(manifest_path, manifest)
        with self.assertRaisesRegex(release.ReleaseError, "one coherent data licence"):
            self.verify()

        manifest["data_license"] = "CC-BY-4.0"
        write_json(manifest_path, manifest)
        (self.root / "verify_manual_release.py").write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(release.ReleaseError, "verifier differs"):
            self.verify()


if __name__ == "__main__":
    unittest.main()
