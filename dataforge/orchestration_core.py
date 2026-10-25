"""Safe, dependency-light building blocks for Prefect orchestration.

The orchestration boundary deliberately keeps credentials in environment
variables, never Prefect task parameters, reports or persisted manifests.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .source import MAX_PAGE_SIZE

ROOT = Path(__file__).resolve().parent.parent
MAX_SCHEDULE_LOOKBACK = 7
MAX_HISTORICAL_BACKFILL_DAYS = 31
DEFAULT_DAILY_RECORD_CAP = 50_000  # Typical NYC311 days exceed 10,000 requests.


class IncompleteWindowError(RuntimeError):
    """The configured record cap may have truncated a date partition."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_window(start: date, end: date, max_records: int, page_size: int) -> None:
    if not isinstance(start, date) or not isinstance(end, date) or end <= start:
        raise ValueError("Window must be a nonempty [start, end) date range")
    if not 1 <= max_records <= 1_000_000:
        raise ValueError("max_records must be in 1..1000000")
    if not 1 <= page_size <= MAX_PAGE_SIZE:
        raise ValueError(f"page_size must be in 1..{MAX_PAGE_SIZE}")


def previous_complete_days(*, lookback_days: int, today: date | None = None):
    """Return bounded calendar windows, oldest first, without claiming UTC source times."""
    if not 1 <= lookback_days <= MAX_SCHEDULE_LOOKBACK:
        raise ValueError(f"lookback_days must be in 1..{MAX_SCHEDULE_LOOKBACK}")
    today = today or datetime.now(timezone.utc).date()
    return [(today - timedelta(days=offset), today - timedelta(days=offset - 1))
            for offset in range(lookback_days, 0, -1)]


def historical_daily_windows(start: date, end: date) -> list[tuple[date, date]]:
    """Plan at most 31 explicit source-local daily windows, oldest first.

    The exclusive end is a calendar boundary, not a conversion to UTC.
    One-day partitions keep the existing manifest completeness gate effective.
    """
    if not isinstance(start, date) or not isinstance(end, date):
        raise ValueError("Backfill start/end must be dates")
    days = (end - start).days
    if not 1 <= days <= MAX_HISTORICAL_BACKFILL_DAYS:
        raise ValueError(
            f"Backfill must span 1..{MAX_HISTORICAL_BACKFILL_DAYS} days; "
            "split larger historical ranges into separate runs"
        )
    return [(start + timedelta(days=i), start + timedelta(days=i + 1))
            for i in range(days)]


def require_database_environment() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required; load it privately from .env")
    if not os.getenv("DBT_PASSWORD"):
        raise RuntimeError("DBT_PASSWORD is required; load it privately from .env")


def require_complete_snapshot(manifest: dict, *, allow_truncated: bool) -> None:
    if manifest.get("dataset_id") != "erm2-nwe9":
        raise ValueError("Incorrect NYC 311 source dataset")
    if manifest.get("reached_max_records") and not allow_truncated:
        raise IncompleteWindowError(
            "Record cap reached: completeness cannot be proven. "
            "Narrow the window/increase max_records, or explicitly opt into a smoke extract."
        )


def find_dbt_executable(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    sibling = Path(sys.executable).with_name("dbt.exe" if os.name == "nt" else "dbt")
    if sibling.is_file():
        return str(sibling)
    detected = shutil.which("dbt")
    if not detected:
        raise RuntimeError("dbt executable not found in the current Python environment")
    return detected


def build_analytics(*, executable: str | None = None, timeout_seconds: int = 900,
                    runner=subprocess.run) -> dict:
    """Call the tested CLI rather than importing dbt's unstable Python internals."""
    require_database_environment()
    if timeout_seconds < 30 or timeout_seconds > 7200:
        raise ValueError("dbt timeout must be in 30..7200 seconds")
    command = [find_dbt_executable(executable), "build", "--project-dir",
               str(ROOT / "dbt"), "--profiles-dir", str(ROOT / "dbt"), "--threads", "2"]
    env = os.environ.copy()
    # Pin to documented Prefect/CLI behavior even if global dbt user settings
    # have enabled the optional State cloud integration.
    env["DBT_ENGINE_MANAGE_STATE"] = "0"
    try:
        process = runner(command, cwd=ROOT, env=env, capture_output=True,
                         text=True, encoding="utf-8", errors="replace",
                         timeout=timeout_seconds, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("dbt build exceeded its configured timeout") from exc
    if process.returncode != 0:
        # Deliberately omit stdout/stderr: they may contain host-specific info
        # or arbitrary custom-macro output. Local dbt/logs provides diagnostics.
        raise RuntimeError(f"dbt build failed (exit code {process.returncode})")
    matches = re.findall(
        r"\bPASS=(\d+)\s+WARN=(\d+)\s+ERROR=(\d+)\s+SKIP=(\d+)\S*.*?\bTOTAL=(\d+)",
        process.stdout or "",
    )
    if not matches:
        raise RuntimeError("dbt returned success without the expected test summary")
    passed, warned, errored, skipped, total = map(int, matches[-1])
    if warned or errored or skipped or not passed:
        raise RuntimeError("dbt quality gate rejected warnings/errors/skipped tests")
    return {"status": "passed", "passed": passed, "total": total,
            "warned": warned, "errored": errored, "skipped": skipped}


def write_evidence(report: dict, output_dir: Path) -> Path:
    """Atomic evidence report without secrets, generated outside version control."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"run_{report['run_id']}.json"
    target = output_dir / filename
    temporary = output_dir / (filename + ".partial")
    try:
        temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def new_report(start: date, end: date, *, max_records: int,
               allow_truncated: bool) -> dict:
    return {
        "run_id": uuid.uuid4().hex,
        "dataset_id": "erm2-nwe9",
        "started_at_utc": utc_now(),
        "finished_at_utc": None,
        "window_start_inclusive": start.isoformat(),
        "window_end_exclusive": end.isoformat(),
        "max_records": max_records,
        "allow_truncated": allow_truncated,
        "status": "running",
        "stage": "preflight",
        "ingestion": None,
        "warehouse": None,
        "dbt": None,
        "error_type": None,
    }

