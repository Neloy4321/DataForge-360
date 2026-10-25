# Power BI Desktop — reproducible report specification

## Offline five-day snapshot starter (no PostgreSQL required)

The four **aggregated** NYC 311 exports from 2026-09-01 through 2026-09-05
are bundled in [`powerbi/demo_exports/`](../powerbi/demo_exports/) for a
reproducible **offline Power BI Desktop** portfolio report. Follow the
[build guide](../powerbi/BUILD_SNAPSHOT_REPORT.md), use the
[separate aggregate-table DAX measures](../powerbi/snapshot_measures.dax),
and verify totals with `python powerbi/validate_demo_exports.py` before
publishing. **Do not relate these four pre-aggregated tables**: use the dbt
star schema below for valid date, agency, borough and complaint cross-filters.
The CSV starter and DAX specification below remain useful for reconstruction.
The project owner saved and provided a **five-page native `.pbix`**
from Windows Power BI Desktop (2026-10-25), now committed to `main` at
[`powerbi/native/`](../powerbi/native/). Static artifact checks passed.
Owner-supplied Desktop screenshots show all five report pages, a Queens
selection that updates the Borough Analytics KPIs and highlights the relevant
bars, and the four CSV tables loading during Refresh; the owner reported that
Refresh completed without error. This is **screenshot-based local acceptance**,
not execution of Windows Desktop by GitHub CI. See
[native report verification](POWER_BI_NATIVE_REPORT.md) and
[local acceptance decision](LOCAL_RELEASE_ACCEPTANCE_2026-10-25.md).

The owner-supplied PBIX uses independent, pre-aggregated CSV tables. It is
**not** the request-grain dbt star schema specified in the sections below.

## Connect to the same local warehouse

1. Start the DataForge PostgreSQL container and run the dbt build first.
2. In Power BI Desktop, **Get Data → PostgreSQL database**.
3. Server: `127.0.0.1:55432`; Database: `dataforge`.
4. Authenticate as your local dataforge account using the password in your
   uncommitted `.env`. Never save this password in Git or screenshots.
5. Choose **Import** mode only for your currently small bounded sample. For
   larger datasets, profile and plan incremental refresh or DirectQuery first.
6. Select tables from schema `analytics_marts`:
   `fct_service_requests`, `dim_agency`, `dim_borough`, `dim_complaint`, `dim_date`.
   Do **not** import the `staging.service_requests` source payload.

## Star-schema relationships

Create single-direction, one-to-many relationships (dimension → fact):

| Dimension (one side) | Fact (many side) |
|---|---|
| `dim_agency.agency_key` | `fct_service_requests.agency_key` |
| `dim_borough.borough_key` | `fct_service_requests.borough_key` |
| `dim_complaint.complaint_key` | `fct_service_requests.complaint_key` |
| `dim_date.date_day` | `fct_service_requests.created_day` |

Do not automatically create additional ambiguous bi-directional relationships.
Use `dim_date.date_day` to filter by created date, not by closed date.

## Measures and dashboard pages

Create the measures in [`powerbi/measures.dax`](../powerbi/measures.dax)
individually in the fact table. Suggested pages:

1. **Executive Overview:** total requests, closed percentage, median valid
   resolution hours, daily volume line chart, borough ranking.
2. **Agency & Problem Performance:** agency and complaint Top N, closure share,
   median resolution, borough/agency slicers.
3. **Data Quality & Coverage:** missing closure timestamps, valid resolution
   observation count, loaded min/max dates, source coverage disclaimer.

Label the report as **bounded NYC 311 sample** until complete source ingestion
is separately demonstrated. The project has no government affiliation. Public
distribution of PBIX data extracts requires a review of privacy and hosting.
