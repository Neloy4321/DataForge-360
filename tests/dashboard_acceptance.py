"""Isolated PostgreSQL acceptance for dashboard queries over real dbt marts.

Requires the four synthetic rows from tests/dbt_acceptance.py and a fully
materialized dbt model in the dedicated dataforge_ci database.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dataforge.analytics import (
    DashboardFilters, extent_query, fetch_rows, metric_query,
)


def main() -> None:
    import psycopg

    dsn = os.environ.get("DATAFORGE_TEST_DATABASE_URL", "")
    if not dsn:
        raise RuntimeError("DATAFORGE_TEST_DATABASE_URL is required")
    with psycopg.connect(dsn) as conn:
        if conn.info.dbname != "dataforge_ci":
            raise RuntimeError("Refusing dashboard acceptance outside dataforge_ci")
    prefix = os.environ.get("DBT_SCHEMA", "analytics_ci")

    def metric(which: str, filters: DashboardFilters) -> list[dict]:
        statement, parameters = metric_query(which, filters, prefix=prefix)
        return fetch_rows(dsn, statement, parameters)

    statement, parameters = extent_query(prefix=prefix)
    extent = fetch_rows(dsn, statement, parameters)[0]
    assert extent == {"first_day": date(2026, 9, 1),
                      "last_day": date(2026, 9, 2), "fact_rows": 4}, extent

    all_rows = DashboardFilters(date(2026, 9, 1), date(2026, 9, 2))
    overview = metric("overview", all_rows)[0]
    assert overview["total_requests"] == 4, overview
    assert overview["closed_requests"] == 2, overview
    assert overview["valid_resolution_count"] == 1, overview
    assert float(overview["median_resolution_hours"]) == 2.0, overview
    assert len(metric("daily", all_rows)) == 2
    borough = {item["label"]: item["requests"]
               for item in metric("borough", all_rows)}
    assert borough == {"BROOKLYN": 2, "UNKNOWN": 1, "QUEENS": 1}, borough
    assert metric("map", all_rows) == [], "Must suppress under-5 geographical cells"

    brooklyn = DashboardFilters(all_rows.start, all_rows.end,
                                boroughs=("BROOKLYN",), statuses=("Closed",))
    filtered = metric("overview", brooklyn)[0]
    assert filtered["total_requests"] == filtered["closed_requests"] == 1
    assert len(metric("daily", brooklyn)) == 1

    missing = DashboardFilters(all_rows.start, all_rows.end, agencies=("MISSING_AGENCY",))
    assert metric("overview", missing)[0]["total_requests"] == 0
    print("PASS: dashboard fact metrics, filters, date grain, valid durations, "
          "read-only queries and location privacy threshold")


if __name__ == "__main__":
    main()
