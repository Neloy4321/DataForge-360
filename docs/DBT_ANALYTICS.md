# Phase 3 — dbt analytics model and acceptance

## Grain, semantics and schemas

`staging.service_requests` is loaded by Phase 2; dbt must not write to it.
`analytics_stg.stg_service_requests` is a view over the operational source.
`analytics_marts` contains:

| Model | Grain | Key | Behavior |
|---|---|---|---|
| `dim_agency` | normalized agency code | `agency_key` | Source-local full name chosen deterministically via `max()` |
| `dim_borough` | normalized borough | `borough_key` | Uppercase/trim, missing bucket |
| `dim_complaint` | normalized complaint type | `complaint_key` | Trim, missing bucket |
| `dim_date` | observed calendar day | `date_day` | Year/quarter/month/ISO weekday |
| `fct_service_requests` | latest known state of one request | `service_request_id` | Date and three category foreign keys; status, ZIP, resolution hours |

Dimensions use `md5(coalesce(cleaned_value, '__MISSING__'))` as deterministic
surrogate keys. `UNKNOWN` appears as a display name for missing source values,
not as a claim about the underlying city record. ZIP codes are kept as text,
including leading zeros.

`resolution_hours` is `closed_at - created_at` in hours when the result is
nonnegative; it is null if the request is still open or if the source dates
contradict one another. A `has_closed_timestamp` indicator describes **date
availability**, not necessarily official final request status.

The source provides timezone-naive timestamps. Do not assume UTC or calculate
absolute SLA compliance until a source timezone/DST policy is independently
verified. Date dimension calendar fields reflect the unconverted source dates.

## Quality gates

- Unique and non-null source/service-request identifiers.
- No missing creation dates.
- Unique, non-null dimension keys and distinct fact request identifiers.
- Fact-to-agency, borough, complaint and date relationships.
- Fact count equals staging count (one-row-per-request contract).
- No negative manufactured `resolution_hours`; null duration for source clock
  contradictions or an absent closing timestamp.
- Boolean closed-timestamp flag always matches closing-date presence.
- Deterministic CI checks using *four synthetic fixture records* for normalized
  labels, `00102` ZIP preservation, 2-hour resolution, null category members,
  invalid reverse timestamps and a second identical build.

The dedicated CI script refuses to seed or query any database other than
`dataforge_ci`. The CI data are artificial and are **not** included in the user's
real NYC 311 analytical figures.

## Verified Windows smoke acceptance — 2026-10-24

The project owner supplied PowerShell output from Windows 11, Python 3.11.9
and the existing PostgreSQL Docker container:

- dbt adapter `1.11.0`; `dbt debug`: profiles/project files valid and connection OK.
- First local `dbt build`: 6 models plus 32 data tests, `PASS=38`, `WARN=0`,
  `ERROR=0`, `SKIP=0`.
- `analytics_marts.fct_service_requests`: 100 records matching the 100-row
  bounded snapshot loaded into operational staging.
- This is a local functional acceptance, not an independent full-data benchmark
  or a signed production deployment claim.

The originally installed resolver selected prerelease `dbt-core 1.13.0b1`,
even with the stable Postgres adapter pinned. The project now also pins
`dbt-core==1.12.6` to prevent accidental beta upgrades in future installations.

## Local run

In Windows PowerShell, within a fresh Git clone of the latest `main`:

```powershell
python -m pip install -r requirements-dbt.txt
$dbPassword = ((Get-Content .env | Where-Object { $_ -match '^POSTGRES_PASSWORD=' } | Select-Object -First 1) -split '=', 2)[1]
$env:DBT_PASSWORD = $dbPassword
$env:DBT_ENGINE_MANAGE_STATE = "0"
dbt debug --project-dir dbt --profiles-dir dbt
dbt build --project-dir dbt --profiles-dir dbt --threads 2
```

The `.env` file is kept locally and never committed. The password is required
by dbt and is not loaded from `.env` automatically. Other connection settings
are optionally overridable using `DBT_HOST`, `DBT_PORT`, `DBT_USER`,
`DBT_DBNAME` and `DBT_SCHEMA`. The custom model schemas are composed by dbt from
the default target schema, for example `analytics_stg` and `analytics_marts`.

dbt State is a separate, account-authenticated cloud optimization feature and
is intentionally **disabled** (`flags.manage_state: false` plus environment
`DBT_ENGINE_MANAGE_STATE=0`). It is unnecessary for locally built,
deterministic analytics tables. If a user's dbt installation opens a sign-in
window and waits for State authentication, cancel, set the environment variable,
and run the documented ordinary dbt build. The `--no-manage-state` option is not
available in dbt Core v1.12; no trial or account signup is required here.

## Future work / honest limitations

- The 100-row successful local snapshot is only a **bounded smoke test**.
  Production-wide historical backfill and performance profiling remain pending.
- Dimensions represent the *current state*, not SCD2; fact rows are neither
  immutable events nor accurate reconstruction of prior complaint status.
- `created_date` ingestion filters alone miss updates to older requests;
  source-side reconciliation/watermarks must be built before continuous sync.
- Table materializations rebuild from staging. Incremental processing,
  partitioning, indexes for analytics and query benchmarks need separate
  acceptance once input scale increases.
- Data may be delayed or updated at source; no source-freshness SLA has been
  demonstrated. No scheduling, dashboard or public deployment is provided by
  Phase 3.

