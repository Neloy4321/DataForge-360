"""Prefect 3 local-first orchestration for DataForge 360.

Manual:   python -m dataforge.prefect_pipeline run --start ... --end ...
Backfill: python -m dataforge.prefect_pipeline backfill --start ... --end ...
Schedule: python -m dataforge.prefect_pipeline serve --cron "0 3 * * *"

Prefect credentials, dbt passwords and database DSNs are never task parameters.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

try:
    from prefect import flow, get_run_logger, task
except ImportError as exc:
    raise RuntimeError(
        "Prefect is optional: install requirements-prefect.txt in the active venv"
    ) from exc

from .orchestration_core import (
    ROOT, DEFAULT_DAILY_RECORD_CAP, build_analytics, historical_daily_windows, new_report, previous_complete_days,
    require_complete_snapshot, require_database_environment, utc_now,
    validate_window, write_evidence,
)
from .pipeline import ingest_window
from .source import NYC311Client
from .warehouse import load_snapshot


@task(name="ingest-nyc311", retries=2, retry_delay_seconds=8)
def ingest_task(start_iso: str, end_iso: str, *, output_dir: str,
                page_size: int, max_records: int) -> dict:
    return ingest_window(
        NYC311Client(), date.fromisoformat(start_iso), date.fromisoformat(end_iso),
        output_dir=Path(output_dir), page_size=page_size, max_records=max_records,
    )


@task(name="load-verified-warehouse", retries=2, retry_delay_seconds=5)
def warehouse_task(snapshot_path: str) -> dict:
    return load_snapshot(Path(snapshot_path), os.environ["DATABASE_URL"])


@task(name="build-dbt-star-schema", retries=1, retry_delay_seconds=5)
def dbt_task() -> dict:
    return build_analytics()


@flow(name="dataforge-360-partition", log_prints=False)
def run_partition_flow(start: str, end: str, *, max_records: int = DEFAULT_DAILY_RECORD_CAP,
                       page_size: int = 1000, allow_truncated: bool = False,
                       output_dir: str = "data/raw",
                       report_dir: str = "data/runs") -> dict:
    """Fetch -> integrity gate -> upsert -> dbt tests, persist success/failure evidence."""
    start_day, end_day = date.fromisoformat(start), date.fromisoformat(end)
    validate_window(start_day, end_day, max_records, page_size)
    require_database_environment()
    raw_base = Path(output_dir)
    if not raw_base.is_absolute():
        raw_base = ROOT / raw_base
    reports = Path(report_dir)
    if not reports.is_absolute():
        reports = ROOT / reports
    report = new_report(start_day, end_day, max_records=max_records,
                        allow_truncated=allow_truncated)
    # Give each run an immutable raw-snapshot directory. A failed/capped retry
    # cannot overwrite the verified source evidence from a prior run.
    raw = raw_base / report["run_id"]
    logger = get_run_logger()
    try:
        report["stage"] = "ingestion"
        manifest = ingest_task(start, end, output_dir=str(raw),
                               page_size=page_size, max_records=max_records)
        report["ingestion"] = {
            "rows_written": manifest["rows_written"],
            "reached_max_records": manifest["reached_max_records"],
            "sha256": manifest["content_sha256_uncompressed"],
            "snapshot": f"{report['run_id']}/{manifest['file']}",
        }
        report["stage"] = "completeness_gate"
        require_complete_snapshot(manifest, allow_truncated=allow_truncated)
        report["stage"] = "warehouse"
        warehouse = warehouse_task(str(raw / manifest["file"]))
        report["warehouse"] = {
            "rows_read": warehouse["rows_read"],
            "rows_inserted_or_updated": warehouse["rows_inserted_or_updated"],
            "rows_unchanged": warehouse["rows_unchanged"],
        }
        if warehouse["rows_read"] != manifest["rows_written"]:
            raise RuntimeError("Warehouse count did not match ingestion manifest")
        report["stage"] = "dbt_quality"
        report["dbt"] = dbt_task()
        report["status"] = "succeeded"
        report["stage"] = "complete"
        logger.info("Validated %d ingested rows with %d new/changed; dbt PASS=%d",
                    manifest["rows_written"], warehouse["rows_inserted_or_updated"],
                    report["dbt"]["passed"])
    except Exception as exc:
        report["status"] = "failed"
        report["error_type"] = type(exc).__name__
        raise
    finally:
        report["finished_at_utc"] = utc_now()
        evidence = write_evidence(report, reports)
        logger.info("Local run evidence saved: %s (status=%s)", evidence, report["status"])
    return report


@flow(name="dataforge-360-daily-reconciliation", log_prints=False)
def refresh_recent_flow() -> list[dict]:
    """Process the most recent complete UTC calendar windows, then exit.

    This operational calendar is not an assertion of the NYC 311 timestamp zone.
    Default: one yesterday partition, conservative completeness checks on.
    """
    days = int(os.getenv("DATAFORGE_LOOKBACK_DAYS", "1"))
    max_records = int(os.getenv("DATAFORGE_MAX_RECORDS_PER_DAY", str(DEFAULT_DAILY_RECORD_CAP)))
    page_size = int(os.getenv("DATAFORGE_PAGE_SIZE", "1000"))
    windows = previous_complete_days(lookback_days=days)
    results = []
    for start, end in windows:
        results.append(run_partition_flow(start.isoformat(), end.isoformat(),
                                          max_records=max_records,
                                          page_size=page_size,
                                          allow_truncated=False))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local-first Prefect NYC 311 ETL/ELT")
    commands = parser.add_subparsers(dest="action", required=True)
    single = commands.add_parser("run", help="One explicit bounded date window")
    single.add_argument("--start", required=True, help="Inclusive YYYY-MM-DD")
    single.add_argument("--end", required=True, help="Exclusive YYYY-MM-DD")
    single.add_argument("--max-records", type=int, default=DEFAULT_DAILY_RECORD_CAP)
    single.add_argument("--page-size", type=int, default=1000)
    single.add_argument("--allow-truncated", action="store_true",
                        help="Explicit smoke-only option; forbids completeness claims")
    backfill = commands.add_parser(
        "backfill", help="Safely replay an explicit 1..31 day historical range"
    )
    backfill.add_argument("--start", required=True, help="Inclusive YYYY-MM-DD")
    backfill.add_argument("--end", required=True, help="Exclusive YYYY-MM-DD")
    backfill.add_argument("--max-records-per-day", type=int, default=DEFAULT_DAILY_RECORD_CAP)
    backfill.add_argument("--page-size", type=int, default=1000)
    backfill.add_argument("--dry-run", action="store_true",
                          help="Print planned daily windows without touching API or database")
    deployment = commands.add_parser("serve", help="Serve a local daily schedule")
    deployment.add_argument("--cron", default="0 3 * * *")
    deployment.add_argument("--lookback-days", type=int, default=1)
    deployment.add_argument("--max-records-per-day", type=int, default=DEFAULT_DAILY_RECORD_CAP)
    deployment.add_argument("--page-size", type=int, default=1000)
    args = parser.parse_args(argv)
    try:
        if args.action == "run":
            require_database_environment()
            output = run_partition_flow(args.start, args.end,
                                        max_records=args.max_records,
                                        page_size=args.page_size,
                                        allow_truncated=args.allow_truncated)
            print(json.dumps({"status": output["status"], "run_id": output["run_id"],
                              "rows_read": output["warehouse"]["rows_read"],
                              "dbt_pass": output["dbt"]["passed"]}, indent=2))
        elif args.action == "backfill":
            windows = historical_daily_windows(date.fromisoformat(args.start),
                                               date.fromisoformat(args.end))
            validate_window(windows[0][0], windows[0][1],
                            args.max_records_per_day, args.page_size)
            if args.dry_run:
                print(json.dumps({
                    "status": "planned",
                    "start_inclusive": args.start,
                    "end_exclusive": args.end,
                    "daily_partitions": len(windows),
                    "max_records_per_day": args.max_records_per_day,
                    "page_size": args.page_size,
                    "days": [start.isoformat() for start, _ in windows],
                }, indent=2))
                return 0
            require_database_environment()
            completed = []
            for start_day, end_day in windows:
                result = run_partition_flow(
                    start_day.isoformat(), end_day.isoformat(),
                    max_records=args.max_records_per_day,
                    page_size=args.page_size,
                    allow_truncated=False,
                )
                completed.append({
                    "day": start_day.isoformat(),
                    "run_id": result["run_id"],
                    "rows_read": result["warehouse"]["rows_read"],
                    "rows_inserted_or_updated": result["warehouse"]["rows_inserted_or_updated"],
                    "rows_unchanged": result["warehouse"]["rows_unchanged"],
                    "dbt_pass": result["dbt"]["passed"],
                })
            print(json.dumps({
                "status": "succeeded",
                "completed_partitions": len(completed),
                "rows_read": sum(item["rows_read"] for item in completed),
                "runs": completed,
            }, indent=2))
        else:
            require_database_environment()
            previous_complete_days(lookback_days=args.lookback_days)
            validate_window(date(2026, 9, 1), date(2026, 9, 2),
                            args.max_records_per_day, args.page_size)
            os.environ["DATAFORGE_LOOKBACK_DAYS"] = str(args.lookback_days)
            os.environ["DATAFORGE_MAX_RECORDS_PER_DAY"] = str(args.max_records_per_day)
            os.environ["DATAFORGE_PAGE_SIZE"] = str(args.page_size)
            refresh_recent_flow.serve(name="dataforge-local-daily", cron=args.cron)
    except (ValueError, OSError, RuntimeError) as exc:
        # Never echo exception messages from arbitrary database or shell tools:
        # credentials can appear in underlying driver error strings.
        print(f"Pipeline failed ({type(exc).__name__}). Check private local logs/evidence.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

