"""Real Prefect + PostgreSQL + dbt acceptance with synthetic NYC 311 records.

CI-only: requires dedicated dataforge_ci; no network fetch and no user records.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

# This acceptance script is invoked directly in CI and on Windows. Python puts
# tests/ (not the repository root) on sys.path for direct script execution.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    import psycopg

    from dataforge.prefect_pipeline import run_partition_flow
    from dataforge.source import NYC311Client

    dsn = os.getenv("DATAFORGE_TEST_DATABASE_URL", "")
    if not dsn:
        raise RuntimeError("Only a configured, dedicated test database can be used")
    with psycopg.connect(dsn) as conn:
        if conn.info.dbname != "dataforge_ci":
            raise RuntimeError("Refusing Prefect integration outside dataforge_ci")
    os.environ["DATABASE_URL"] = dsn
    os.environ["DBT_ENGINE_MANAGE_STATE"] = "0"
    rows = [
        {"unique_key": "df_prefect_ci_1", "created_date": "2026-09-01T10:00:00",
         "agency": "DOT", "borough": "Brooklyn", "complaint_type": "Pothole",
         "incident_zip": "00102", "status": "Open"},
        {"unique_key": "df_prefect_ci_2", "created_date": "2026-09-01T11:00:00",
         "closed_date": "2026-09-01T12:00:00", "agency": "DEP",
         "borough": "Queens", "complaint_type": "Water", "status": "Closed"},
    ]
    def synthetic_page(url: str, headers: dict) -> list[dict]:
        # Match the API's $limit contract: a cap=1 smoke check must receive
        # one record, allowing the completeness gate itself to be exercised.
        limit = int(parse_qs(urlsplit(url).query)["$limit"][0])
        return rows[:limit]

    client = NYC311Client(fetch=synthetic_page, app_token="")

    with tempfile.TemporaryDirectory() as folder:
        raw, evidence = str(Path(folder) / "raw"), str(Path(folder) / "evidence")
        with patch("dataforge.prefect_pipeline.NYC311Client", return_value=client):
            first = run_partition_flow("2026-09-01", "2026-09-02",
                                       max_records=20, page_size=10,
                                       output_dir=raw, report_dir=evidence)
            second = run_partition_flow("2026-09-01", "2026-09-02",
                                        max_records=20, page_size=10,
                                        output_dir=raw, report_dir=evidence)

        assert first["status"] == second["status"] == "succeeded"
        assert first["warehouse"]["rows_read"] == 2
        assert first["warehouse"]["rows_inserted_or_updated"] == 2
        assert second["warehouse"]["rows_inserted_or_updated"] == 0
        assert second["warehouse"]["rows_unchanged"] == 2
        assert first["dbt"]["passed"] == second["dbt"]["passed"] == 38
        files = list(Path(evidence).glob("run_*.json"))
        assert len(files) == 2 and all(json.loads(f.read_text())["status"] == "succeeded"
                                       for f in files)
        assert not list(Path(raw).glob("*.partial"))
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select count(*) from staging.service_requests where "
                            "unique_key like 'df_prefect_ci_%'")
                assert cur.fetchone()[0] == 2
                cur.execute("select count(*) from analytics_prefect_ci_marts.fct_service_requests")
                assert cur.fetchone()[0] == 2

        # A deliberately capped extract must fail *before* any warehouse mutation.
        with patch("dataforge.prefect_pipeline.NYC311Client", return_value=client):
            try:
                run_partition_flow("2026-09-01", "2026-09-02", max_records=1,
                                   page_size=1, output_dir=raw, report_dir=evidence)
            except Exception:
                pass
            else:
                raise AssertionError("Truncated window was incorrectly accepted")
        failed = [json.loads(p.read_text()) for p in Path(evidence).glob("run_*.json")
                  if json.loads(p.read_text())["status"] == "failed"]
        assert len(failed) == 1 and failed[0]["stage"] == "completeness_gate"
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select count(*) from staging.service_requests where "
                            "unique_key like 'df_prefect_ci_%'")
                assert cur.fetchone()[0] == 2
    print("PASS: Prefect ingestion -> checksums -> PostgreSQL -> dbt; replay and cap rejection")


if __name__ == "__main__":
    main()

