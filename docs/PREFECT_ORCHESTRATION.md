# Phase 4 — Prefect 3 orchestration

## Orchestrated contract

`python -m dataforge.prefect_pipeline` is the executable entry point. It
offers a manually bounded `run` mode and an **opt-in** local `serve` deployment.
Neither mode requires a Prefect Cloud or dbt Cloud account.

Each manual window runs in this precise sequence:

1. Preflight checks: valid date window, bounded page/cap settings and presence
   of database connection environment variables. No credentials are passed as
   Prefect task parameters or written into evidence.
2. Prefect task `ingest-nyc311`: fetch from official API, retry transient
   failures, atomically write `.jsonl.gz` plus SHA-256 manifest in a unique
   `data/raw/<run-id>/` folder. Failed/capped runs cannot overwrite prior raw
   window evidence. Historical snapshots require a future retention policy.
3. Completeness gate: **stop** if `reached_max_records=true` unless an explicit
   *smoke-only* `--allow-truncated` flag was supplied. Capping at the exact
   source length remains conservatively classified as incomplete.
4. Prefect task `load-verified-warehouse`: independently verify manifest,
   validate rows and upsert via PostgreSQL transactions. Re-running an unchanged
   snapshot should yield zero changed rows.
5. Prefect task `build-dbt-star-schema`: run dbt through its CLI and verify a
   nonzero passing test summary with no skipped/error/warning tests.
6. Atomically save the run's success/failure report to the Git-ignored
   `data/runs/run_<random-id>.json` file.

Task retries do not make all three systems one atomic transaction. If dbt
fails, a valid staging load can remain while marts reflect an older build.
Rerun the same window after addressing the issue. The report's `stage` and
`status` identify which step failed. Reports are local, unsigned operational
artifacts, not externally verified deployment evidence.

## Windows PowerShell — first manual smoke run

Keep the *existing* DataForge Docker PostgreSQL container running. From the
`DataForge-360-git` clone, with your `.env` already copied locally:

```powershell
git pull --ff-only origin main
.\.venv\Scripts\python.exe -m pip install -r requirements-warehouse.txt -r requirements-dbt.txt -r requirements-prefect.txt
$dbPassword = ((Get-Content .env | Where-Object { $_ -match '^POSTGRES_PASSWORD=' } | Select-Object -First 1) -split '=', 2)[1]
$env:DATABASE_URL = 'postgresql://dataforge:' + [System.Uri]::EscapeDataString($dbPassword) + '@127.0.0.1:55432/dataforge'
$env:DBT_PASSWORD = $dbPassword
$env:DBT_ENGINE_MANAGE_STATE = '0'
.\.venv\Scripts\python.exe -m dataforge.prefect_pipeline run --start 2026-09-01 --end 2026-09-02 --max-records 100 --page-size 50 --allow-truncated
```

The smoke flag is intentional for the previously tested 100-row sample. It is
**not** evidence of a complete date backfill. The pipeline will rerun the dbt
models and report on unchanged versus updated rows. Expect the first Prefect
run to take longer than the existing standalone commands because the local
Prefect orchestration engine initializes its state database.

## Opt-in local daily scheduling (not started by default)

Only after successful manual validation: start a local Prefect server in a
separate PowerShell window, from the same installed Python environment:

```powershell
.\.venv\Scripts\prefect.exe server start
```

Prefect's UI is usually available at `http://127.0.0.1:4200` while the server
is running. In another PowerShell terminal, activate the same local database
password environment variables listed above and set the local API address:

```powershell
$env:PREFECT_API_URL = 'http://127.0.0.1:4200/api'
.\.venv\Scripts\python.exe -m dataforge.prefect_pipeline serve --cron '0 3 * * *' --lookback-days 1 --max-records-per-day 10000 --page-size 1000
```

`serve` stays running and listens for scheduled flow runs; stopping that
process with Ctrl+C stops its listener. Scheduling is not a permanent Windows
service, cloud deployment or guarantee of daily execution after a laptop
shutdown. Configure a Windows service or hosted worker *later*, after local
acceptance and resource profiling.

Scheduled mode defaults to processing one previously completed UTC calendar
date interval. This **does not** assert NYC 311 uses UTC timestamps; source
time-zone and DST semantics remain unverified. A configurable maximum of seven
daily intervals enables a small overlap for late updates, not arbitrary CDC.
An incomplete date window fails closed rather than silently importing a
truncated dataset. Increase `--max-records-per-day` or subdivide the date
range before scheduling heavy historical loads; the laptop has 8 GB RAM.

## Acceptance and limitations

- `tests/test_orchestration_core.py`: deterministic offline safeguards,
  time-window validation, cap policy, dbt error-handling and private evidence.
- `tests/prefect_acceptance.py`: isolated GitHub Actions PostgreSQL job using
  **synthetic** NYC311-style records, not live production/network data. It
  executes the actual Prefect flow twice, verifies replay-safe upserts and
  dbt facts, then confirms a capped extract is rejected before loading.
  The automated CI acceptance passed on GitHub Actions; this is not proof of
  sustained operation or of a user-run Windows deployment.
- No scheduling service or user-run Prefect flow has yet been accepted on
  Windows. No claims of production availability, live-site alerts, full-data
  throughput or independent operational sign-off are made.

