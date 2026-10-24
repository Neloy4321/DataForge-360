import gzip
import hashlib
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from dataforge.pipeline import ingest_window
from dataforge.source import NYC311Client


class PipelineTests(unittest.TestCase):
    start = date(2026, 9, 1)
    end = date(2026, 9, 8)

    @staticmethod
    def client_with(rows):
        return NYC311Client(fetch=lambda url, headers: rows, app_token="")

    def test_atomic_export_and_manifest_integrity(self):
        rows = [{"unique_key": "1", "created_date": "2026-09-02T09:00:00", "agency": "DOT"}]
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            manifest = ingest_window(self.client_with(rows), self.start, self.end,
                                     output_dir=out, page_size=10, max_records=10)
            content = gzip.decompress(next(out.glob("*.jsonl.gz")).read_bytes())
            self.assertEqual([json.loads(x)["unique_key"] for x in content.splitlines()], ["1"])
            self.assertEqual(manifest["content_sha256_uncompressed"], hashlib.sha256(content).hexdigest())
            self.assertEqual(manifest["rows_written"], 1)
            self.assertFalse(list(out.glob("*.partial")))

    def test_repeat_run_replaces_window_instead_of_appending(self):
        rows = [{"unique_key": "1", "created_date": "2026-09-02T09:00:00"}]
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            for _ in range(2):
                manifest = ingest_window(self.client_with(rows), self.start, self.end,
                                         output_dir=out, page_size=10, max_records=10)
            self.assertEqual(len(list(out.glob("*.jsonl.gz"))), 1)
            self.assertEqual(manifest["rows_written"], 1)

    def test_invalid_page_does_not_publish_partial_snapshot(self):
        rows = [{"unique_key": "1", "created_date": "2026-08-20T09:00:00"}]
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            with self.assertRaises(ValueError):
                ingest_window(self.client_with(rows), self.start, self.end,
                              output_dir=out, page_size=10, max_records=10)
            self.assertEqual(list(out.iterdir()), [])

    def test_invalid_date_window_does_not_write(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                ingest_window(self.client_with([]), self.end, self.start,
                              output_dir=Path(temp))


if __name__ == "__main__":
    unittest.main()
