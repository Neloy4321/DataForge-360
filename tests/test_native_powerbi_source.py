"""Offline fail-closed acceptance for the editable native Power BI report."""
import tempfile
import unittest
import zipfile
from pathlib import Path
from shutil import copytree

from powerbi.validate_native_release import verify_pbip_report_parity


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "powerbi/native/DataForge360_Cinematic_v5.1.pbix"
PROJECT = ROOT / "powerbi/native/source/DataForge360_PowerBI"


class NativePowerBISourceTests(unittest.TestCase):
    def test_complete_report_matches_saved_pbix(self):
        with zipfile.ZipFile(REPORT) as archive:
            observed = verify_pbip_report_parity(archive, PROJECT)
        self.assertEqual(observed["source_visuals"], 86)
        self.assertEqual(observed["registered_resource_files"], 6)

    def test_missing_visual_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder) / "project"
            copytree(PROJECT, temp)
            visual = next(temp.rglob("visual.json"))
            visual.unlink()
            with zipfile.ZipFile(REPORT) as archive, self.assertRaisesRegex(
                ValueError, "missing|file set"
            ):
                verify_pbip_report_parity(archive, temp)

    def test_changed_visual_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder) / "project"
            copytree(PROJECT, temp)
            visual = next(temp.rglob("visual.json"))
            visual.write_text('{"wrong":"report"}', encoding="utf-8")
            with zipfile.ZipFile(REPORT) as archive, self.assertRaisesRegex(
                ValueError, "differs"
            ):
                verify_pbip_report_parity(archive, temp)

    def test_missing_registered_resource_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder) / "project"
            copytree(PROJECT, temp)
            resource = next(temp.rglob("DataForgeCinematic-*.png"))
            resource.unlink()
            with zipfile.ZipFile(REPORT) as archive, self.assertRaisesRegex(
                ValueError, "missing"
            ):
                verify_pbip_report_parity(archive, temp)


if __name__ == "__main__":
    unittest.main()
