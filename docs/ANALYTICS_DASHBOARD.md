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

- The initial 100-row September 1 smoke extract was deliberately truncated.
  In later owner-supplied Windows execution, five source-created days
  (September 1–5, 2026) were loaded and reconciled to **50,740** fact rows.
  Screenshot evidence shows 50,740 requests, 47,101 Closed (92.8%) and
  6.1-hour median valid closure time with all category filters cleared.
  Those five dates do **not** establish complete citywide historical coverage.
- Daily trend dates use **ordered source-local date categories**, not a continuous
  timestamp axis. This avoids the misleading `12 PM` ticks previously seen
  between whole-day points; each tooltip retains its ISO date.
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
  and only cells with **five or more requests** appear. The map displays at most
  **400** qualifying grid cells, so additional eligible cells can be omitted.
  Tiny samples often have no eligible map cells; that is normal.
- Initial date range defaults to the last 30 **available** created days. The
  app limits an arbitrary user-selected window to 367 calendar dates and
  caps top-category rows, map groups and cache entries. PostgreSQL statements
  have a 20-second timeout and use read-only transactions.
- Large backfills need suitable warehouse indexes/partitioning, profiling,
  source completeness checks and controlled hosting *before* claiming scale.

## Evidence and local acceptance

Automated GitHub Actions CI passed using synthetic cases, validating SQL results,
privacy grouping and the real Streamlit app runtime. The owner supplied Windows
screenshots for the five-day dashboard, including the filtered Activity,
Operations and Geographic Clusters views. These are accepted for the tested
local dashboard scope; automated validation of every BI download control is
not separately claimed.

The native Power BI `.pbix` and editable `.pbip` were committed to `main`
in `4f783f6`. Owner-supplied Windows evidence supports all five page visuals,
Queens borough-selection behavior, and the four CSV source loads during
Refresh; the owner reported that Refresh finished without an error.
See [local release acceptance](LOCAL_RELEASE_ACCEPTANCE_2026-10-25.md).

**Only future milestone:** hosting, benchmarking and comprehensive end-to-end
acceptance, deferred by the owner. This includes public authentication,
unattended scheduling reliability and independent full-pipeline evidence.
No production-hosting claim is made.
