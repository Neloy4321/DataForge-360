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

## Local run

In Windows PowerShell, within a fresh Git clone of the latest `main`:

```powershell
python -m pip install -r requirements-dbt.txt
$dbPassword = ((Get-Content .env | Where-Object { $_ -match '^POSTGRES_PASSWORD=' } | Select-Object -First 1) -split '=', 2)[1]
$env:DBT_PASSWORD = $dbPassword
dbt debug --project-dir dbt --profiles-dir dbt
dbt build --project-dir dbt --profiles-dir dbt --threads 2
```

The `.env` file is kept locally and never committed. The password is required
by dbt and is not loaded from `.env` automatically. Other connection settings
are optionally overridable using `DBT_HOST`, `DBT_PORT`, `DBT_USER`,
`DBT_DBNAME` and `DBT_SCHEMA`. The custom model schemas are composed by dbt from
the default target schema, for example `analytics_stg` and `analytics_marts`.

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

