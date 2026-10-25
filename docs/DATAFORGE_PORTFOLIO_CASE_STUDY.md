# DataForge 360 — portfolio case study

## Problem and product

NYC 311 service-request data requires careful ingestion, validation and
explanation before city-service trends can be interpreted responsibly.
DataForge 360 is an **independent data engineering and analytics portfolio
project** that connects a bounded open-data ingestion pipeline with a
reproducible warehouse, analytics and two reporting surfaces.

## Architecture

1. **Python + NYC Open Data API:** keyset pagination, bounded date windows,
   retries, validation, atomic gzip JSONL snapshots and SHA-256 manifests.
2. **PostgreSQL:** request-grain staging and replay-safe upserts.
3. **dbt:** four dimensional tables plus request-grain fact, with source,
   relationship and quality tests.
4. **Prefect:** retry-aware local workflows, a completeness guard, dbt quality
   gate and locally recorded run evidence.
5. **Streamlit:** database-backed read-only operational exploration.
6. **Power BI Desktop:** an independent five-day historical **aggregate CSV**
   showcase comprising five polished visual pages; not a live warehouse feed.

## Measured five-day sample

The supplied aggregate CSV files reconcile to **50,740** service requests,
**47,101** marked Closed and **3,639** not Closed, a **92.83%** status-based
close-out ratio. The Top-15 complaints comprise **30,763** requests (60.63%
of the total), not all complaint categories.

This snapshot uses creation dates (September 1–5, 2026). Closure flags
represent a later observed status; the chart does not assert closures happened
on the same date, and the ratio is not an SLA or live NYC-wide statistic.

## Quality and reproducibility

GitHub includes offline Python tests, PostgreSQL integration, dbt tests,
Prefect acceptance checks and Streamlit dashboard checks. The repository
README records bounded Windows and GitHub CI evidence; those historical runs
must not be confused with re-execution during this PBIX handoff.

The native Power BI artifact has five report pages, 86 native visuals,
five decorative backgrounds, and an included editable `.pbip` source.
Artifact structure and aggregate reconciliation were inspected in the
release package. The owner reported successful Windows Power BI usage and
saving of the final `.pbix`; independent automated visual rendering is pending.

## Honest limitations and future work

- Source-completeness and any scheduler uptime require independent testing.
- The five-day import is static and CSV-based, not live/incremental.
- Cross-filtering aggregate tables would create misleading comparisons; the
  request-grain dbt star schema must be used for integrated analysis.
- Source record statuses can change after their creation dates.
- Request-level privacy and embedded data sources must be reviewed before
  publishing native PBIX files publicly.
- No claim of official NYC agency endorsement or production deployment.

## Relevant skills

**Python, REST APIs, PostgreSQL, dimensional modeling, dbt, Prefect,
SQL, data quality, automated testing, Streamlit, Power BI, DAX,
analytics communication and reproducibility.**
