from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image

from claimkit.demo import generate_demo
from claimkit.evaluate import evaluate_demo
from claimkit.export import export_package
from claimkit.extract import normalize_date, normalize_price
from claimkit.models import ReviewStatus
from claimkit.ocr import SidecarOCRBackend
from claimkit.pipeline import create_claim_package, inspect_folder
from claimkit.quality import image_quality_warnings


class ClaimKitTests(unittest.TestCase):
    def test_normalization(self) -> None:
        self.assertEqual(normalize_date("18/08/2026"), "2026-08-18")
        self.assertEqual(normalize_price("54 990,00", "₽"), "54990.00 RUB")

    def test_end_to_end_demo_and_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            evidence_dir = generate_demo(root / "evidence")
            package, evidence = create_claim_package(evidence_dir, "en", "Crack on the appliance door")
            truth = json.loads((evidence_dir / "ground-truth.json").read_text())
            self.assertEqual(len(evidence), truth["files"])
            serials = {
                field.normalized_value for field in package.extracted_fields if field.name == "serial_number"
            }
            self.assertEqual(serials, {truth["serial_number"]})
            model_conflicts = [c for c in package.conflicts if c.field_name == "model"]
            self.assertEqual(len(model_conflicts), 1)
            self.assertEqual(model_conflicts[0].competing_values, truth["expected_model_conflict"])
            self.assertEqual(package.missing_evidence, [])

            self.assertTrue(package.damage_suggestions)
            package.damage_suggestions[0].user_status = ReviewStatus.CONFIRMED
            package.confirmed_damage = [package.damage_suggestions[0]]

            archive = export_package(root / "package", package, evidence, "en")
            self.assertTrue(archive.exists())
            with zipfile.ZipFile(archive) as bundle:
                names = set(bundle.namelist())
                self.assertIn("manifest.json", names)
                self.assertIn("claim-summary.pdf", names)
                self.assertIn("claim-letter-en.txt", names)
                self.assertIn("confirmed-damage/damage-01.png", names)
                manifest = json.loads(bundle.read("manifest.json"))
                manifest_text = json.dumps(manifest)
                self.assertNotIn(str(root), manifest_text)
                self.assertTrue(
                    all(item["path"].startswith("originals/") for item in manifest["evidence"])
                )
                self.assertIn("confirmed-damage/damage-01.png", manifest["package"]["output_files"])

    def test_quality_and_non_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image_path = root / "flat.png"
            Image.new("RGB", (200, 100), "white").save(image_path)
            warnings = image_quality_warnings(image_path)
            self.assertIn("low_resolution", warnings)
            self.assertIn("overexposed", warnings)
            evidence_dir = generate_demo(root / "evidence")
            package, evidence = create_claim_package(evidence_dir)
            output = root / "occupied"
            output.mkdir()
            (output / "keep.txt").write_text("user data")
            with self.assertRaises(FileExistsError):
                export_package(output, package, evidence)
            self.assertEqual((output / "keep.txt").read_text(), "user data")

    def test_exact_duplicate_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            first = folder / "first.png"
            second = folder / "second.png"
            Image.new("RGB", (320, 240), "gray").save(first)
            second.write_bytes(first.read_bytes())
            evidence, _ = inspect_folder(folder, ocr=SidecarOCRBackend())
            duplicate_warnings = [
                warning
                for item in evidence
                for warning in item.quality_warnings
                if warning.startswith("duplicate_of:")
            ]
            self.assertEqual(duplicate_warnings, ["duplicate_of:first.png"])

    def test_evaluation_thresholds(self) -> None:
        result = evaluate_demo()
        self.assertGreaterEqual(result["normalized_field_recall"], 0.9)
        self.assertEqual(result["conflict_recall"], 1.0)


if __name__ == "__main__":
    unittest.main()
