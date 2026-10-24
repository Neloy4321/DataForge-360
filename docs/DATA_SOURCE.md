# Data source, provenance and field contract

## Primary source

- **Owner:** NYC Open Data / NYC311
- **Dataset:** [311 Service Requests from 2020 to Present](https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2020-to-Present/erm2-nwe9)
- **Identifier:** `erm2-nwe9`
- **API:** `https://data.cityofnewyork.us/resource/erm2-nwe9.json`
- **Developer reference:** [Socrata API](https://dev.socrata.com/foundry/data.cityofnewyork.us/fhrw-4uyv)
- **Data dictionary:** `311_ServiceRequest_2020-present_DataDictionary_Updated_2025.xlsx`, published with the dataset (maintained externally; not copied into the code repository)
- **Accessed:** 2026-10-24; source is updated daily, so record values may change.

The supplied official Excel dictionary was reviewed. Its `Column Information`
sheet includes the 44 public-facing columns; other sheets describe agency,
problem, descriptor, location-type mappings and the dataset's revision history.
The 2025 revision changed some displayed names. Use API field names in code.

## Selected ingestion fields

| Display concept | API field | Notes |
|---|---|---|
| Unique Key | `unique_key` | Text identifier; do not coerce to integer |
| Created Date | `created_date` | Source-local timestamp, no UTC assumption |
| Closed Date | `closed_date` | Nullable for unresolved requests |
| Agency / Agency Name | `agency`, `agency_name` | Operational ownership |
| Problem / Problem Detail | `complaint_type`, `descriptor` | Controlled categories evolve |
| Status | `status` | May be revised after initial creation |
| Resolution Action Updated | `resolution_action_updated_date` | Update signal; not yet used for CDC |
| Borough / ZIP / Community Board | `borough`, `incident_zip`, `community_board` | ZIP remains text |
| Intake Channel | `open_data_channel_type` | Often optional |
| Coordinates | `latitude`, `longitude` | Optional numeric-like source values |

The initial pipeline avoids street addresses and free-text resolution details.
Published data does not reveal customer identity according to the source's
description, but downstream public dashboards should still aggregate geographic
and operational metrics rather than expose record-level locations.

## Engineering cautions

- Use an API application token through `NYC311_APP_TOKEN` when available; never
  commit it. Anonymous access may be rate limited.
- Expected category values can change. Do not hardcode exhaustive mappings.
- Future incremental ingest must revisit mutable records and upsert by
  `unique_key`; a created-date-only high watermark is insufficient.
- Keep raw extracts and their manifests out of Git. Reproduce them with the CLI.
- Dataset availability or API behavior can change; report live failures rather
  than inventing successful data pulls.
