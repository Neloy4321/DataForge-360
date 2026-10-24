"""CLI acceptance: planning must be bounded and require no DB credentials or API."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def command(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("DATABASE_URL", None)
    env.pop("DBT_PASSWORD", None)
    return subprocess.run(
        [sys.executable, "-m", "dataforge.prefect_pipeline", "backfill", *args],
        cwd=ROOT, env=env, text=True, capture_output=True, timeout=90, check=False,
    )


def main() -> None:
    result = command("--start", "2026-09-01", "--end", "2026-09-03",
                     "--max-records-per-day", "50000", "--page-size", "1000",
                     "--dry-run")
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan["status"] == "planned", plan
    assert plan["daily_partitions"] == 2, plan
    assert plan["days"] == ["2026-09-01", "2026-09-02"], plan

    invalid = command("--start", "2026-09-01", "--end", "2026-10-03",
                      "--dry-run")
    assert invalid.returncode != 0, "32-day request must fail before any IO"
    print("Bounded backfill CLI dry-run PASS (no database credentials)")


if __name__ == "__main__":
    main()
