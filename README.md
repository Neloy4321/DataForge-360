# DataForge 360

**Enterprise Data Engineering & Analytics Platform — NYC 311 · Ingestion · PostgreSQL · dbt · Prefect · BI**

[![Python CI](https://github.com/Neloy4321/DataForge-360/actions/workflows/ci.yml/badge.svg)](https://github.com/Neloy4321/DataForge-360/actions/workflows/ci.yml)

DataForge 360 is a portfolio-oriented, reproducible data-engineering project
built around real public NYC 311 service-request data. The end goal is an
end-to-end platform with ingestion, a PostgreSQL warehouse, dbt transformations,
Prefect orchestration, quality checks, BI analysis and a web dashboard.

**Status:** Bounded API ingestion, a PostgreSQL staging warehouse with replay-safe
upserts, and SQL analytics models with dbt quality tests are implemented.
Phase 2's PostgreSQL integration checks passed GitHub Actions. On 2026-10-24,
the project owner also verified ingestion of 100 real NYC 311 records, a matching
SHA-256 manifest, warehouse loading of 100 rows, and a PostgreSQL count of 100
on Windows. Phase 3's dbt build, data tests, exact-value integration checks and
rebuild verification passed GitHub Actions (run 40105753201). The project owner
independently ran `dbt debug` successfully on Windows and completed the real-data
dbt build with **38/38 PASS (6 models, 32 tests, 0 warnings/errors)**, including
`analytics_marts.fct_service_requests` with **100 rows** on 2026-10-24.
Phase 4 adds a local-first Prefect flow with task retries, a conservative
incomplete-window guard, replay-safe staging, a dbt quality gate, atomic run
evidence and an opt-in daily local schedule. Five CI jobs passed on its final
merged commit; the owner then verified the real Windows 100-row Prefect smoke
run (**38 dbt passes, zero changed rows on replay, succeeded**) on 2026-10-24.
This is bounded smoke validation, not full-window or scheduler acceptance.
Phase 5 introduces a read-only Streamlit analytics dashboard and a reproducible
Power BI Desktop specification. Synthetic PostgreSQL+dbt metrics and the actual
Streamlit app both passed isolated GitHub Actions CI; The project owner has now saved and supplied a five-page cinematic native
Power BI `.pbix` on Windows (2026-10-25); the supplied binary passed static
archive/definition checks, but independent GUI rendering and a full refresh
have not been executed here. The **binary is not yet committed** to GitHub;
see [native Power BI handoff](docs/POWER_BI_NATIVE_REPORT.md).

## What works today

- Query the official NYC 311 API for an explicit half-open date window.
- Collect records in small batches using keyset pagination, not an unstable
  unbounded offset loop.
- Select operational fields while excluding address and free-text detail.
- Reject malformed identifiers, out-of-range timestamps and non-advancing pages.
- Retry transient HTTP errors, including 429 and 503 with `Retry-After` support.
- Write gzip JSONL snapshots through a temporary file, then atomically replace
  the file for its date window. A rerun does not append duplicate files.
- Produce a JSON manifest with row count, source, time window and SHA-256 digest.
- Run a deterministic offline unit-test suite through Python's standard library.
- Upsert a verified snapshot into PostgreSQL staging without rewriting unchanged rows.
- Produce dbt staging views, four dimensions, and one request-grain fact table.
- Assert source uniqueness, star-schema relationships, fact counts and valid durations.
- Execute ingestion, warehouse load and dbt quality gates as Prefect tasks with
  bounded retries and per-run local evidence; opt in to local daily scheduling.
- Explore aggregated service-request KPIs, trends, agency/problem rankings and
  approximate geographic clusters through a bounded read-only Streamlit dashboard.

## Quick start

Requires **Python 3.11+**. Phase 1 has no third-party Python dependencies.

```bash
git clone https://github.com/Neloy4321/DataForge-360.git
cd DataForge-360
python -m unittest discover -s tests -v
```

Collect up to 10,000 records for one week (end date is **exclusive**):

```bash
python -m dataforge --start 2026-09-01 --end 2026-09-08 --max-records 10000 --page-size 1000
```

For a low-memory smoke test, use `--max-records 7 --page-size 5`. The CLI writes
only to `data/raw/` by default; this directory is excluded from Git. The two
outputs have names like:

```text
data/raw/nyc311_2026-09-01_2026-09-08.jsonl.gz
data/raw/nyc311_2026-09-01_2026-09-08.manifest.json
```

On PowerShell, the equivalent run is:

```powershell
python -m dataforge --start 2026-09-01 --end 2026-09-08 --max-records 10000 --page-size 1000
```

The optional Socrata app token is passed by environment variable:

```powershell
$env:NYC311_APP_TOKEN = "your-app-token"
```

Do **not** put real secrets in the repository. The `.env.example` file is only
a reference; the Phase 1 CLI does not automatically load `.env` files.

## Verification

```bash
python -m unittest discover -s tests -v
python -m compileall -q dataforge tests
```

During initial development (2026-10-24), the Phase 1 offline suite passed
**13/13** tests. The expanded Phase 2 suite passed 19 local unit tests, with
the separate database integration test skipped until PostgreSQL is available.
A live NYC API smoke check successfully fetched 5 records and a second
two-page run fetched 7 records, with a manifest and checksum. These small
integration checks do **not** demonstrate full backfill or production throughput.
GitHub Actions independently tests the code on each push and pull request.

## Phase 2 — PostgreSQL staging warehouse

The optional warehouse loader requires PostgreSQL 16 and Psycopg 3. On Windows,
keep Docker Desktop open and make sure `docker ps` succeeds first. Use a local
password that you do not publish. With PowerShell in the repository folder:

```powershell
Copy-Item .env.example .env
notepad .env
```

In `.env`, replace `POSTGRES_PASSWORD` with a strong local password. Then:

```powershell
docker compose up -d
python -m pip install -r requirements-warehouse.txt
python -m dataforge --start 2026-09-01 --end 2026-09-02 --max-records 100 --page-size 50
```

Set a `DATABASE_URL` environment variable using the **same** local password,
URL-encoded if it contains reserved URL characters:

```powershell
$env:DATABASE_URL = "postgresql://dataforge:YOUR_URL_ENCODED_PASSWORD@127.0.0.1:55432/dataforge"
python -m dataforge.warehouse --input data/raw/nyc311_2026-09-01_2026-09-02.jsonl.gz
```

The loader creates the staging schema and indexes, verifies the raw snapshot's
record count and SHA-256, checks every record, and upserts in small transactions.
Run the same command again: unchanged rows should not be rewritten. A changed
status in a re-collected snapshot updates the matching `unique_key` without
creating a second row. The loader reports rows read, changed and unchanged.

PostgreSQL is bound to `127.0.0.1:55432` for local use; Docker data lives in a
named volume. Do not delete the volume unless you intend to remove local data.
See [warehouse implementation and limitations](docs/WAREHOUSE.md).

## Phase 3 — dbt analytics star schema

The `dbt/` project creates a clean staging view, **four dimension tables**
(`dim_agency`, `dim_borough`, `dim_complaint`, `dim_date`) and the
`fct_service_requests` table. Each fact row represents one current service
request, keyed by the original text identifier. Foreign keys are deterministic
hashes of normalized source values; missing category values map to an `UNKNOWN`
dimension member. Resolution hours are computed only when the source closing
timestamp is not before its creation timestamp. Source-local timestamps are
**not** silently converted to UTC.

The default development target writes its views to `analytics_stg` and tables
to `analytics_marts`. It **does not** modify `staging.service_requests`.

On Windows PowerShell, after the PostgreSQL load above, install the dbt adapter
and set its secret from your existing uncommitted `.env` file:

```powershell
python -m pip install -r requirements-dbt.txt
$dbPassword = ((Get-Content .env | Where-Object { $_ -match '^POSTGRES_PASSWORD=' } | Select-Object -First 1) -split '=', 2)[1]
$env:DBT_PASSWORD = $dbPassword
$env:DBT_ENGINE_MANAGE_STATE = "0"
dbt debug --project-dir dbt --profiles-dir dbt
dbt build --project-dir dbt --profiles-dir dbt --threads 2
```

No password is printed or placed on the command line. The dbt target defaults
to localhost port 55432, username `dataforge`, and database `dataforge`.
The dbt dependency file pins supported stable `dbt-core==1.12.6` and
`dbt-postgres==1.11.0`; older installs may have resolved to prerelease
`dbt-core==1.13.0b1` and should reinstall from the updated requirements.
We explicitly disable the unrelated **dbt State** cloud integration in the
project configuration and with `DBT_ENGINE_MANAGE_STATE=0`. This project needs
**no dbt account, dbt State trial, browser sign-in or hosted dbt platform**.
If an existing installation prompts for State login, cancel with Ctrl+C,
set `$env:DBT_ENGINE_MANAGE_STATE = "0"`, and retry the normal dbt build.
Core v1.12 does not expose the newer `--no-manage-state` CLI option.
Run `dbt build` again after reloading a changed snapshot to refresh the marts.

To check the analytics data using your existing Docker container:

```powershell
docker compose exec -T postgres psql -U dataforge -d dataforge -c "SELECT count(*) FROM analytics_marts.fct_service_requests;"
docker compose exec -T postgres psql -U dataforge -d dataforge -c "SELECT agency_code, count(*) AS requests FROM analytics_marts.fct_service_requests f JOIN analytics_marts.dim_agency a USING (agency_key) GROUP BY agency_code ORDER BY requests DESC LIMIT 5;"
```

For the first 100-row bounded ingestion, expect 100 fact rows when the build
passes. The dbt `build` command executes models and data tests in dependency
order. The project checks source and dimension key uniqueness, non-null keys,
dimension relationships, fact row count, duration consistency, and closed-date
flag consistency. The GitHub CI dbt job additionally uses four isolated
**synthetic** records to test ZIP code leading zeros, case normalization,
2-hour resolution, unknown dimensions, bad source-clock handling, and a
repeatable second build. The CI fixtures are not real research results.

See [dbt model contract and limitations](docs/DBT_ANALYTICS.md).

## Phase 4 — Prefect local orchestration

Prefect is optional and installed in the same isolated project venv. It
orchestrates bounded API ingestion, validates snapshot completeness and hashes,
upserts into PostgreSQL, rebuilds dbt analytics, and only then records success.
Task retries and errors are tracked by Prefect. A run's local JSON evidence
is saved under the ignored `data/runs/` folder even after failure. No secrets
or public records are copied into Git.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-warehouse.txt -r requirements-dbt.txt -r requirements-prefect.txt
$dbPassword = ((Get-Content .env | Where-Object { $_ -match '^POSTGRES_PASSWORD=' } | Select-Object -First 1) -split '=', 2)[1]
$env:DATABASE_URL = 'postgresql://dataforge:' + [System.Uri]::EscapeDataString($dbPassword) + '@127.0.0.1:55432/dataforge'
$env:DBT_PASSWORD = $dbPassword
.\.venv\Scripts\python.exe -m dataforge.prefect_pipeline run --start 2026-09-01 --end 2026-09-02 --max-records 100 --page-size 50 --allow-truncated
```

`--allow-truncated` is **for explicit bounded smoke tests only**. Normal and
scheduled runs reject date windows reaching the cap because those extracts
cannot be certified complete. Prefect's daily record cap now defaults to
**50,000**, based on observed real days exceeding 10,000; hitting the cap
still fails closed. A new `backfill` command previews and then
replays at most 31 explicit one-day windows with the same integrity and dbt
quality gates. For backfill instructions and opt-in daily scheduling, see the
[Prefect runbook](docs/PREFECT_ORCHESTRATION.md). Scheduling is not activated
merely by installing or cloning the project.

## Phase 5 — Streamlit dashboard and Power BI-ready analytics

The optional Streamlit app displays actual dbt fact/dimension aggregates—no
fabricated dashboard numbers or local CSV needed. Date and category filters
are bound to read-only PostgreSQL SQL; tiny geographic groups are suppressed
and downloads contain aggregated measures only. With the local container and
dbt marts ready:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-warehouse.txt -r requirements-dashboard.txt
$dbPassword = ((Get-Content .env | Where-Object { $_ -match '^POSTGRES_PASSWORD=' } | Select-Object -First 1) -split '=', 2)[1]
$env:DATABASE_URL = 'postgresql://dataforge:' + [System.Uri]::EscapeDataString($dbPassword) + '@127.0.0.1:55432/dataforge'
.\.venv\Scripts\python.exe -m streamlit run dataforge/dashboard_app.py --server.address 127.0.0.1 --server.port 8501
```

Open `http://127.0.0.1:8501`. No public port, DB password or API key should
be exposed. See the [dashboard runbook](docs/ANALYTICS_DASHBOARD.md) and
[Power BI Desktop model and DAX](docs/POWER_BI.md). A separate Windows-saved native `.pbix` has been provided by the owner and
inspected structurally; it remains to be installed into this Git repository
through the local binary release handoff. See [native report notes](docs/POWER_BI_NATIVE_REPORT.md).

## Native Power BI Desktop delivery (2026-10-25)

The project owner provided a Windows-saved cinematic Power BI report with **five
pages** (Executive, Agency, Borough, Complaint, Quality) and a historical
September 1–5, 2026 aggregate snapshot (**50,740** requests; **47,101**
marked Closed; Top-15 complaints **30,763** requests). The PBIX container,
embedded report definitions and included CSV aggregate totals passed static
checks. The owner reported successful Windows opening, page navigation and
save; an independent Windows Desktop test/refresh was **not run here**.

The four report CSVs are separate aggregates, **not** the PostgreSQL/dbt
request-grain star schema; no valid cross-filtering across the aggregate
tables is implied. This is a non-live portfolio snapshot, not an official
NYC dashboard or an SLA. The binary PBIX is part of the owner's local
release handoff and **not yet committed to the repository**; avoid making
a public-download claim until that Git step is completed.

- [Native PBIX verification and release instructions](docs/POWER_BI_NATIVE_REPORT.md)
- [Portfolio case study](docs/DATAFORGE_PORTFOLIO_CASE_STUDY.md)

## Post-backfill data quality report

After loading multiple complete daily windows, run a read-only daily
reconciliation of staging against the dbt request-grain fact table. It checks
nonempty date coverage, equal daily row counts and unique fact IDs, and
separately reports missing operational fields and anomalous closure timestamps.
A structural PASS **does not** mean NYC source data has zero missing values or
that API completeness was independently audited.

```powershell
.\.venv\Scripts\python.exe -m dataforge.quality_report --start 2026-09-01 --end 2026-09-06
```

With `DATABASE_URL` set, the JSON report is written to the ignored
`data/runs/quality/` directory. See the [quality-report runbook](docs/DATA_QUALITY_REPORT.md).

## Architecture and provenance

- [Current and planned architecture](docs/ARCHITECTURE.md)
- [Official dataset, data dictionary, selected fields and caveats](docs/DATA_SOURCE.md)
- [dbt dimensional model, validation and local runbook](docs/DBT_ANALYTICS.md)
- [Prefect flows, local scheduler, test contract and run evidence](docs/PREFECT_ORCHESTRATION.md)
- [Interactive Streamlit dashboard and BI acceptance](docs/ANALYTICS_DASHBOARD.md)
- [Power BI Desktop star schema, model relationships and measures](docs/POWER_BI.md)
- [Read-only data quality and staging/fact reconciliation report](docs/DATA_QUALITY_REPORT.md)

## Milestones

| Stage | Deliverable | Status |
|---|---|---|
| 1 | Bounded real API ingestion + tests + CI | Implemented; local tests and small live API check passed |
| 2 | PostgreSQL staging, replay-safe upserts and integration tests | Implemented; GitHub PostgreSQL CI passed and user confirmed local 100-row load |
| 3 | dbt transformations, star schema and data quality | Implemented; GitHub dbt CI and user Windows 38/38 local dbt acceptance passed |
| 4 | Prefect orchestration, retries and observability | Isolated Prefect+PostgreSQL+dbt CI passed; user-provided Windows logs show five successful non-capped daily source windows (50,740 rows read), including a three-day backfill; scheduler and independent database reconciliation pending |
| 5 | Streamlit/Power BI analytics | Dashboard SQL + Streamlit UI verified in GitHub CI; user-supplied Windows screenshots confirm five-day 50,740-row Activity, Operations and aggregated-map views; owner saved native Power BI `.pbix` on Windows; binary Git commit and independent Desktop visual test pending |
| 6 | Hosting, benchmarking, end-to-end acceptance | Planned |

## Privacy and limitations

Only a subset of operational fields is pulled. No raw data or API token is
committed. Created-date filtering is suitable for a bounded extract but is **not
yet** an incremental change-data-capture solution: existing service requests
can change status after creation. Further milestones must handle reconciliation,
late updates, warehouse upserts and audit evidence.

This is an independent portfolio project using NYC Open Data; it is not an
official NYC311 application or endorsed by New York City.
