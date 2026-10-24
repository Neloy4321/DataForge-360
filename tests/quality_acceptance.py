"""Validate aggregated quality report against four synthetic dbt CI records."""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dataforge.quality_report import build_quality_report


def main() -> None:
    dsn = os.getenv("DATAFORGE_TEST_DATABASE_URL")
    assert dsn, "Dedicated CI DSN required"
    import psycopg
    with psycopg.connect(dsn) as conn:
        assert conn.info.dbname == "dataforge_ci", "Refuse non-isolated database"
    report = build_quality_report(dsn, date(2026, 9, 1), date(2026, 9, 3),
                                  prefix=os.getenv("DBT_SCHEMA", "analytics_ci"))
    assert report["status"] == "passed", report
    assert report["days_checked"] == 2, report
    assert (report["staging_rows"], report["fact_rows"]) == (4, 4), report
    assert [r["staging_rows"] for r in report["days"]] == [2, 2], report
    assert report["days"][1]["source_quality_observations"][
        "negative_close_interval"] == 1, report
    assert report["days"][1]["source_quality_observations"][
        "missing_agency"] == 1, report
    print("PASS: synthetic staging/fact reconciliation and observable quality warnings")


if __name__ == "__main__":
    main()
