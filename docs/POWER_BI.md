# Power BI Desktop — reproducible report specification

This is a **Power BI-ready analytical model**, not a prebuilt `.pbix` file.
Native `.pbix` creation and Windows visual verification require Power BI Desktop.

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
