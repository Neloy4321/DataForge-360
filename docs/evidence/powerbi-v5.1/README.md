# DataForge 360 — Power BI Desktop evidence (2026-10-25)

Owner-provided screenshots of the actual Power BI V5.1 Desktop report, reviewed for **bounded local portfolio acceptance**. These captures are evidence of what is visible on screen. They are **not** a substitute for independent automation, an externally witnessed audit, production benchmarking or hosted end-to-end acceptance.

| Image | Screenshot evidence |
|---|---|
| [01_executive_overview.png](01_executive_overview.png) | Executive Overview — full snapshot |
| [02_agency_performance.png](02_agency_performance.png) | Agency Performance — full snapshot |
| [03_borough_analytics_clean.png](03_borough_analytics_clean.png) | Borough Analytics — clean, unselected baseline |
| [04_complaint_intelligence.png](04_complaint_intelligence.png) | Complaint Intelligence — top 15 category scope |
| [05_data_quality_method.png](05_data_quality_method.png) | Data Quality & Method — source and aggregation caveats |
| [06_queens_selection.png](06_queens_selection.png) | Borough Analytics — Queens selected, KPIs/visual highlighting updated |
| [07_refresh_dialog_in_progress.png](07_refresh_dialog_in_progress.png) | Desktop refresh dialog — four CSV sources visibly loading (not completion proof) |

## What the screenshots establish

- All five native report pages are visibly rendered, legible, and show expected KPI values for the historical September 1–5, 2026 created-date snapshot.
- Borough Analytics baseline: 50,740 requests, 47,101 marked closed, 92.83%. Selecting Queens on the same page yields 12,493 requests, 11,349 marked closed and 90.84% — consistent with selection highlighting and page KPI filtering.
- The last image is explicitly a **refresh-in-progress** dialog listing `daily`, `agency`, `borough` and `complaint` CSVs. The owner additionally reported no refresh error after the operation. The image by itself does not show a separate finished/succeeded log.
- The source report uses four independent pre-aggregated CSVs, **not** the database-backed dbt star schema. Do not interpret Queens page selection as valid cross-filtering across aggregate tables.
- Snapshot closure-rate status is **not** an SLA, not real-time and not evidence of when cases were closed.

## Acceptance

See [local acceptance](../../LOCAL_RELEASE_ACCEPTANCE_2026-10-25.md).
**Hosting, benchmarking and full end-to-end acceptance remain deferred by the owner.**

## Image integrity

The file hashes in `screenshot_manifest.json` refer to the screenshot bytes as supplied by the owner and renamed for the evidence release.
