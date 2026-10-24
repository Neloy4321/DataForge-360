# Data quality and staging-to-mart reconciliation

This operational check runs **read-only SQL** against PostgreSQL staging and
the current dbt fact table. It emits aggregate-only daily metrics; it never
includes NYC source payloads, individual request IDs, addresses, secrets or
coordinates. It is useful after manual or historical Prefect backfills.

## Run from Windows PowerShell

After completing the five daily September 1–5, 2026 windows and running dbt
successfully, from the `DataForge-360-git` project folder:

```powershell
git pull --ff-only origin main
$dbPassword = ((Get-Content .env | Where-Object { $_ -match '^POSTGRES_PASSWORD=' } | Select-Object -First 1) -split '=', 2)[1]
$env:DATABASE_URL = 'postgresql://dataforge:' + [System.Uri]::EscapeDataString($dbPassword) + '@127.0.0.1:55432/dataforge'
$env:DBT_SCHEMA = 'analytics'
.\.venv\Scripts\python.exe -m dataforge.quality_report --start 2026-09-01 --end 2026-09-06
```

Dates follow the source-local calendar. `--start` is inclusive and `--end`
is exclusive. Report generation is capped at 31 days per invocation, just like
the bounded historical backfill. There is no source API access or mutation.

A summary prints to the console. A detailed JSON report is also written
atomically under the ignored `data/runs/quality/run_<id>.json` directory.
Store that JSON privately unless reviewing its disclosure implications.

## Structural checks (PASS/FAIL)

For every requested day:

1. The staging table contains at least one row. A missing date is flagged,
   rather than silently treating an unprocessed day as a complete zero.
2. Staging and dbt fact table **counts agree** for the source-created day.
3. Fact service request IDs are unique within the day.

Any failed day causes the command to return a nonzero exit status. These checks
help catch missing transformations, stale marts and fact grain issues. Count
equality alone does not prove row-by-row identity or full API coverage.

## Source-quality observations (not automatically failed)

Per-day counts separately record:

- Missing agency, complaint type, borough and status.
- Requests marked Closed with no closed timestamp.
- Closing timestamps earlier than creation timestamps.
- Available nonnegative fact resolution durations.

These are **observable data characteristics** in NYC Open Data, not blanket
pipeline defects. They are not silently converted to zero. The `passed`
structural status must never be described as 100% error-free public data.

## Acceptance scope

- Unit tests exercise matching/mismatching daily counts, missing dates,
  identifier injection rejection, 31-day window limits and warnings.
- GitHub CI executes the report against the **four synthetic dbt fixtures**
  in isolated PostgreSQL and checks expected daily counts/anomalies.
- On the user's Windows laptop, the reported five NYC source partitions total
  **50,740 rows read** across the five dates. That is user-supplied pipeline
  evidence, not a verified current database count until the report is run.
- This report does not establish live scheduling availability, source API
  completeness, a full CDC feed, cryptographic sign-off or production SLOs.
