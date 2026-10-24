"""No database/network needed to test offline Power BI export validation."""

import csv
import tempfile
import unittest
from pathlib import Path

from powerbi.validate_demo_exports import validate


TAG = "2026-09-01_2026-09-05"


class ExportContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)
        self.rows = {
            "daily": [["2026-09-01", "6", "5"], ["2026-09-02", "4", "3"]],
            "agency": [["A", "8", "7", "1.5"], ["B", "2", "1", "3.0"]],
            "borough": [["X", "7", "6", "2"], ["Y", "3", "2", ""]],
            "complaint": [["Issue", "5", "4", "1"]],
        }
        self._write()

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self):
        for kind, rows in self.rows.items():
            fields = ("day", "requests", "closed_requests") if kind == "daily" else (
                "label", "requests", "closed_requests", "median_resolution_hours"
            )
            with (self.directory / f"dataforge_{kind}_{TAG}.csv").open("w", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(fields)
                writer.writerows(rows)

    def test_valid_export(self):
        result = validate(self.directory, TAG)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["other_complaint_requests"], 5)

    def test_mismatched_aggregate_fails(self):
        self.rows["agency"][0][1] = "7"
        self._write()
        with self.assertRaisesRegex(ValueError, "totals disagree"):
            validate(self.directory, TAG)

    def test_duplicate_group_fails(self):
        self.rows["borough"][1][0] = "X"
        self._write()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate(self.directory, TAG)

    def test_closed_over_requested_fails(self):
        self.rows["complaint"][0][2] = "6"
        self._write()
        with self.assertRaisesRegex(ValueError, "closed exceeds"):
            validate(self.directory, TAG)

    def test_unsafe_label_fails(self):
        self.rows["complaint"][0][0] = "=HYPERLINK()"
        self._write()
        with self.assertRaisesRegex(ValueError, "unsafe formula"):
            validate(self.directory, TAG)

    def test_invalid_median_fails(self):
        self.rows["agency"][0][3] = "NaN"
        self._write()
        with self.assertRaisesRegex(ValueError, "invalid median"):
            validate(self.directory, TAG)


if __name__ == "__main__":
    unittest.main()
