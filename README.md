# DataForge 360

**Enterprise Data Engineering & Analytics Platform — Phase 1: NYC 311 ingestion**

[![Python CI](https://github.com/Neloy4321/DataForge-360/actions/workflows/ci.yml/badge.svg)](https://github.com/Neloy4321/DataForge-360/actions/workflows/ci.yml)

DataForge 360 is a portfolio-oriented, reproducible data-engineering project
built around real public NYC 311 service-request data. The end goal is an
end-to-end platform with ingestion, a PostgreSQL warehouse, dbt transformations,
Prefect orchestration, quality checks, BI analysis and a web dashboard.

**Status:** The bounded ingestion layer is implemented and tested. The warehouse,
workflow scheduler, transformations and dashboard are planned and are **not**
presented as completed features.

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

During initial development (2026-10-24), the offline suite passed **13/13**
tests. A live NYC API smoke check successfully fetched 5 records and a second
two-page run fetched 7 records, with a manifest and checksum. These small
integration checks do **not** demonstrate full backfill or production throughput.
GitHub Actions will independently test the code on each push and pull request.

## Architecture and provenance

- [Current and planned architecture](docs/ARCHITECTURE.md)
- [Official dataset, data dictionary, selected fields and caveats](docs/DATA_SOURCE.md)

## Milestones

| Stage | Deliverable | Status |
|---|---|---|
| 1 | Bounded real API ingestion + tests + CI | Code and tests implemented; CI workflow included |
| 2 | PostgreSQL staging/warehouse, deduplication and updates | Planned |
| 3 | dbt transformations, star schema and data quality | Planned |
| 4 | Prefect orchestration, retries and observability | Planned |
| 5 | Streamlit/Power BI analytics | Planned |
| 6 | Hosting, benchmarking, end-to-end acceptance | Planned |

## Privacy and limitations

Only a subset of operational fields is pulled. No raw data or API token is
committed. Created-date filtering is suitable for a bounded extract but is **not
yet** an incremental change-data-capture solution: existing service requests
can change status after creation. Further milestones must handle reconciliation,
late updates, warehouse upserts and audit evidence.

This is an independent portfolio project using NYC Open Data; it is not an
official NYC311 application or endorsed by New York City.
