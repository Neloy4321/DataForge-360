"""Real PostgreSQL integration test; uses only a dedicated test DSN."""

import os
import tempfile
import unittest
import uuid
from datetime import date
from pathlib import Path

from dataforge.pipeline import ingest_window
from dataforge.source import NYC311Client
from dataforge.warehouse import load_snapshot


@unittest.skipUnless(os.getenv("DATAFORGE_TEST_DATABASE_URL"),
                     "requires dedicated DATAFORGE_TEST_DATABASE_URL")
class WarehouseIntegrationTests(unittest.TestCase):
    def test_insert_replay_and_status_update(self):
        import psycopg

        dsn = os.environ["DATAFORGE_TEST_DATABASE_URL"]
        key = "df_test_" + uuid.uuid4().hex
        records = [{
            "unique_key": key,
            "created_date": "2026-09-01T11:00:00",
            "status": "Open",
            "agency": "DOT",
            "incident_zip": "00102",
        }]
        client = NYC311Client(fetch=lambda url, headers: records, app_token="")
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            try:
                ingest_window(client, date(2026, 9, 1), date(2026, 9, 2),
                              output_dir=folder)
                snapshot = next(folder.glob("*.jsonl.gz"))
                first = load_snapshot(snapshot, dsn, batch_size=1)
                again = load_snapshot(snapshot, dsn, batch_size=1)
                self.assertEqual(first["rows_inserted_or_updated"], 1)
                self.assertEqual(again["rows_inserted_or_updated"], 0)
                self.assertEqual(again["rows_unchanged"], 1)

                records[0] = {**records[0], "status": "Closed",
                              "closed_date": "2026-09-01T12:00:00"}
                ingest_window(client, date(2026, 9, 1), date(2026, 9, 2),
                              output_dir=folder)
                updated = load_snapshot(snapshot, dsn, batch_size=1)
                self.assertEqual(updated["rows_inserted_or_updated"], 1)

                with psycopg.connect(dsn) as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT count(*), max(status), max(incident_zip) "
                                    "FROM staging.service_requests WHERE unique_key = %s", (key,))
                        count, status, zipcode = cur.fetchone()
                self.assertEqual((count, status, zipcode), (1, "Closed", "00102"))
            finally:
                with psycopg.connect(dsn) as conn:
                    with conn.cursor() as cur:
                        # Clean up only the precise record created by this test.
                        cur.execute("DELETE FROM staging.service_requests WHERE unique_key = %s", (key,))


if __name__ == "__main__":
    unittest.main()
