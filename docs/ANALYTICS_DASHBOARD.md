# Phase 5 — NYC 311 analytics dashboard

## What is delivered

- `dataforge/analytics.py`: bounded, parameterized, **read-only** SQL over
  `analytics_marts` (or `<DBT_SCHEMA>_marts`) fact and dimensions. Queries compute
  daily volumes, closed-status share, durations, borough/agency/problem rankings
  and approximate location densities inside PostgreSQL. No full fact extracts.
- `dataforge/dashboard_app.py`: Streamlit UI with an inclusive date window,
  borough/agency/problem/status filters, KPI cards, line and bar charts,
  approximate geographic clusters and **aggregate-only** CSV downloads.
- `tests/test_analytics_unit.py`: offline SQL composition and safety checks.
- `tests/dashboard_acceptance.py`: four synthetic records seeded into an isolated
  CI PostgreSQL database, materialized with real dbt models, then checked via
  the production query functions. No live NYC API or personal data in CI.
- `docs/POWER_BI.md` and `powerbi/measures.dax`: a reproducible plan for a
  separate Power BI Desktop report, using the *same* dbt star schema.

## Start the local dashboard on Windows

Prerequisites: Docker Desktop running, DataForge PostgreSQL healthy on port
`55432`, the dbt build already successful, and the project's `.venv` in use.

From the **DataForge-360-git** directory in PowerShell:

```powershell
git pull --ff-only origin main
.\.venv\Scripts\python.exe -m pip install -r requirements-warehouse.txt -r requirements-dashboard.txt
$dbPassword = ((Get-Content .env | Where-Object { $_ -match '^POSTGRES_PASSWORD=' } | Select-Object -First 1) -split '=', 2)[1]
$env:DATABASE_URL = 'postgresql://dataforge:' + [System.Uri]::EscapeDataString($dbPassword) + '@127.0.0.1:55432/dataforge'
$env:DBT_SCHEMA = 'analytics'
.\.venv\Scripts\python.exe -m streamlit run dataforge/dashboard_app.py --server.address 127.0.0.1 --server.port 8501
```

Open `http://127.0.0.1:8501` in a browser. Stop with Ctrl+C.
**Only localhost is intentionally supported at this stage.** Never publish
the local port or send the DSN/password. Public hosting and authentication
are explicitly Phase 6 tasks.

### Interpretation and performance

- On the owner's initial bounded 100-row NYC 311 smoke extract, the UI should
  show **100** total requests when the full loaded two-day interval is selected.
  That sample is *not* evidence of the whole city's request totals.
- `Closed requests` is based on the current `status` field being "Closed";
  it is not based solely on the existence of a closing timestamp.
- Resolution hours are non-null only for valid source timestamps; invalid,
  missing and negative intervals are excluded from mean and median.
- The fact is the latest ingested state *per request*, not a change-event log.
  Existing requests may change after their creation; new extraction windows
  alone do not provide change data capture or guaranteed full coverage.
- Timestamps are reported in their **source-local/unspecified time basis**.
  No unsupported UTC conversion is claimed.
- To reduce exposed location precision, geocoordinates are rounded to 0.01°
  and only cells with **five or more requests** appear. Tiny samples often
  have no eligible map cells; that is normal.
- Initial date range defaults to the last 30 **available** created days. The
  app limits an arbitrary user-selected window to 367 calendar dates and
  caps top-category rows, map groups and cache entries. PostgreSQL statements
  have a 20-second timeout and use read-only transactions.
- Large backfills need suitable warehouse indexes/partitioning, profiling,
  source completeness checks and controlled hosting *before* claiming scale.

## Evidence and unfinished acceptance

Automated GitHub Actions CI passed using synthetic cases, validating SQL results,
privacy grouping and the real Streamlit app runtime (run `40118189903`).
The owner still needs to run the dashboard on Windows,
inspect screenshots and optionally create a native `.pbix` through Power BI
Desktop. No native PBIX or public Streamlit deployment is asserted here.
