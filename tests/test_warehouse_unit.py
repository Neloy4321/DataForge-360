import gzip
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from dataforge.pipeline import ingest_window
from dataforge.source import NYC311Client
from dataforge.warehouse import normalize_record, verify_snapshot


class WarehouseUnitTests(unittest.TestCase):
    start = date(2026, 9, 1)
    end = date(2026, 9, 2)

    def test_normalized_row_preserves_zip_and_timestamp(self):
        row = normalize_record({
            "unique_key": "00123", "created_date": "2026-09-01T11:00:00.000",
            "incident_zip": "00102", "latitude": "40.5", "longitude": "-73.8",
        })
        self.assertEqual(row[0], "00123")
        self.assertEqual(row[10], "00102")
        self.assertIsNone(row[1].tzinfo)
        self.assertEqual(row[13], 40.5)
        self.assertEqual(row[14], -73.8)

    def test_hash_changes_when_status_changes(self):
        record = {"unique_key": "1", "created_date": "2026-09-01T11:00:00", "status": "Open"}
        first = normalize_record(record)
        second = normalize_record({**record, "status": "Closed"})
        self.assertNotEqual(first[15], second[15])
        self.assertEqual(first[15], normalize_record(record)[15])

    def test_invalid_coordinate_is_rejected(self):
        record = {"unique_key": "1", "created_date": "2026-09-01T11:00:00", "latitude": "nan"}
        with self.assertRaisesRegex(ValueError, "latitude outside"):
            normalize_record(record)

    def test_missing_key_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unique_key"):
            normalize_record({"created_date": "2026-09-01T11:00:00"})

    def test_manifest_reconciles_real_gzip_snapshot(self):
        rows = [{"unique_key": "1", "created_date": "2026-09-01T11:00:00"}]
        client = NYC311Client(fetch=lambda url, headers: rows, app_token="")
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            ingest_window(client, self.start, self.end, output_dir=folder)
            snapshot = next(folder.glob("*.jsonl.gz"))
            manifest = verify_snapshot(snapshot)
            self.assertEqual(manifest["rows_written"], 1)
            with gzip.open(snapshot, "ab") as output:
                output.write(b'{"unique_key":"2","created_date":"2026-09-01T11:00:00"}\n')
            with self.assertRaisesRegex(ValueError, "row-count mismatch"):
                verify_snapshot(snapshot)

    def test_modified_manifest_hash_is_rejected(self):
        rows = [{"unique_key": "1", "created_date": "2026-09-01T11:00:00"}]
        client = NYC311Client(fetch=lambda url, headers: rows, app_token="")
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            ingest_window(client, self.start, self.end, output_dir=folder)
            snapshot = next(folder.glob("*.jsonl.gz"))
            manifest_path = next(folder.glob("*.manifest.json"))
            manifest = json.loads(manifest_path.read_text())
            manifest["content_sha256_uncompressed"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                verify_snapshot(snapshot)


if __name__ == "__main__":
    unittest.main()
