"""Read-only NYC 311 staging-to-mart quality and reconciliation report.

Aggregates only: never serialize source_payload, addresses, row identifiers or DSN.
The structural gate does not certify source completeness or accuracy of labels.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import date
from typing import Callable

from .analytics import fetch_rows, marts_schema
from .orchestration_core import ROOT, historical_daily_windows, utc_now, write_evidence

STAGING_SQL = """
SELECT created_date::date AS day,
       count(*) AS rows,
       count(*) FILTER (WHERE nullif(btrim(agency), '') IS NULL) AS missing_agency,
       count(*) FILTER (WHERE nullif(btrim(complaint_type), '') IS NULL) AS missing_complaint,
       count(*) FILTER (WHERE nullif(btrim(borough), '') IS NULL) AS missing_borough,
       count(*) FILTER (WHERE nullif(btrim(status), '') IS NULL) AS missing_status,
       count(*) FILTER (WHERE lower(btrim(coalesce(status, ''))) = 'closed'
                                AND closed_date IS NULL) AS closed_without_timestamp,
       count(*) FILTER (WHERE closed_date < created_date) AS negative_close_interval
FROM staging.service_requests
WHERE created_date >= %s AND created_date < %s
GROUP BY created_date::date ORDER BY 1
""".strip()


def fact_daily_sql(prefix: str) -> str:
    schema = marts_schema(prefix)
    return f"""
SELECT created_day AS day,
       count(*) AS rows,
       count(DISTINCT service_request_id) AS distinct_ids,
       count(resolution_hours) AS valid_resolution_count
FROM {schema}."fct_service_requests"
WHERE created_day >= %s AND created_day < %s
GROUP BY created_day ORDER BY 1
""".strip()


def _by_day(rows: list[dict]) -> dict[str, dict]:
    return {str(row["day"]): row for row in rows}


def build_quality_report(dsn: str, start: date, end: date, *,
                         prefix: str = "analytics",
                         fetch: Callable = fetch_rows) -> dict:
    """Aggregate daily structural checks and transparent source-data warnings."""
    windows = historical_daily_windows(start, end)
    parameters = (start, end)
    facts_query = fact_daily_sql(prefix)  # Validate schema before any DB work.
    staging = _by_day(fetch(dsn, STAGING_SQL, parameters))
    facts = _by_day(fetch(dsn, facts_query, parameters))
    days: list[dict] = []
    for day, _ in windows:
        key = day.isoformat()
        stage = staging.get(key, {})
        fact = facts.get(key, {})
        stage_rows = int(stage.get("rows", 0))
        fact_rows = int(fact.get("rows", 0))
        distinct_ids = int(fact.get("distinct_ids", 0))
        checks = {
            "nonempty_staging_day": stage_rows > 0,
            "staging_fact_row_count_match": stage_rows == fact_rows,
            "unique_fact_request_ids": fact_rows == distinct_ids,
        }
        warnings = {
            column: int(stage.get(column, 0))
            for column in (
                "missing_agency", "missing_complaint", "missing_borough",
                "missing_status", "closed_without_timestamp",
                "negative_close_interval",
            )
        }
        days.append({
            "day": key,
            "staging_rows": stage_rows,
            "fact_rows": fact_rows,
            "unique_fact_ids": distinct_ids,
            "valid_resolution_count": int(fact.get("valid_resolution_count", 0)),
            "structural_checks": checks,
            "source_quality_observations": warnings,
            "structural_status": "passed" if all(checks.values()) else "failed",
        })
    failed = [item["day"] for item in days if item["structural_status"] != "passed"]
    return {
        "run_id": uuid.uuid4().hex,
        "generated_at_utc": utc_now(),
        "source": "NYC 311 erm2-nwe9; source-local created dates, not UTC-normalized",
        "start_inclusive": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "status": "failed" if failed else "passed",
        "scope": "staging-to-fact structural reconciliation (not API completeness)",
        "days_checked": len(days),
        "staging_rows": sum(item["staging_rows"] for item in days),
        "fact_rows": sum(item["fact_rows"] for item in days),
        "failed_days": failed,
        "days": days,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only NYC311 data quality report")
    parser.add_argument("--start", required=True, help="Inclusive YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="Exclusive YYYY-MM-DD")
    parser.add_argument("--dbt-schema", default=os.getenv("DBT_SCHEMA", "analytics"))
    args = parser.parse_args(argv)
    try:
        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            raise RuntimeError("DATABASE_URL must be set locally")
        report = build_quality_report(
            dsn, date.fromisoformat(args.start), date.fromisoformat(args.end),
            prefix=args.dbt_schema,
        )
        report_path = write_evidence(report, ROOT / "data" / "runs" / "quality")
        summary = {
            "status": report["status"],
            "days_checked": report["days_checked"],
            "staging_rows": report["staging_rows"],
            "fact_rows": report["fact_rows"],
            "failed_days": report["failed_days"],
            "daily_breakdown": [
                {"day": day["day"], "staging_rows": day["staging_rows"],
                 "fact_rows": day["fact_rows"],
                 "structural_status": day["structural_status"]}
                for day in report["days"]
            ],
            "local_evidence": str(report_path.relative_to(ROOT)),
        }
        print(json.dumps(summary, indent=2))
        return 0 if report["status"] == "passed" else 1
    except Exception as exc:
        # Database exceptions may contain connection details; never print messages.
        print(f"Quality report failed ({type(exc).__name__}). See private local logs.",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
