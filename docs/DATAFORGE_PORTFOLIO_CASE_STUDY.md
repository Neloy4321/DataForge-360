# DataForge 360 — portfolio case study

## Challenge and solution

Create a reproducible analytics platform around the real NYC 311 public service-request feed. The Python ingestion layer uses bounded time windows, keyset pagination, defensive validation and atomic raw snapshots with hashes. PostgreSQL staging implements replay-safe upserts; dbt produces a request-grain star schema; Prefect coordinates retries, quality gates and local execution evidence. A read-only Streamlit app explores the modeled data.

A separate **five-page Power BI Desktop report** presents a historical September 1–5, 2026 snapshot from four independent aggregate CSV exports. It is **not a live PostgreSQL connection** and must not be presented as such.

## Measured sample

The four exports reconcile to 50,740 requests, 47,101 marked Closed, and 3,639 not Closed (92.83% closure-status ratio). Top-15 complaint types account for 30,763 requests, or around 60.63% of the observed total. The figures are historical created-window observations; close-out does not mean a closure event occurred on the creation date and is not a service-level guarantee.

## Evidence and limitations

The repository contains offline Python tests and CI workflows for PostgreSQL, dbt, Prefect and Streamlit. Earlier README evidence describes bounded local Windows runs and synthetic CI tests. Those historical results are **not equivalent to fresh full-window, real-world deployment acceptance**.

The owner supplied a native five-page Windows-saved PBIX. This file passed static container and definition checks; the Desktop rendering and refresh have not been independently automated in this environment. The binary release still requires committing through an authenticated local Git client. See [Native report handoff](POWER_BI_NATIVE_REPORT.md).

Next steps: end-to-end reproducibility on the full input window, late-status change handling, scheduler evidence, data-quality monitoring, performance measurements, and a request-grain/warehouse-connected Power BI report.

**Skills:** Python, data ingestion, REST APIs, PostgreSQL, SQL, dbt, dimensional modeling, Prefect, GitHub Actions, Streamlit, DAX, Power BI, data quality and technical communication.