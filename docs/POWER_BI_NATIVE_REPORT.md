# Power BI — native cinematic report verification and handoff

**Snapshot:** NYC Open Data 311 service requests, created September 1–5, 2026.
**Artifact:** Windows Power BI Desktop-saved `DataForge360_Cinematic_v5.1.pbix`.
**Validation date:** 2026-10-25.

## Report contents

| Page | Native visuals |
|---|---:|
| Executive Overview | 19 |
| Agency Performance | 17 |
| Borough Analytics | 16 |
| Complaint Intelligence | 15 |
| Data Quality & Method | 19 |

Total: **86 native visuals**, plus five decorative cinematic background resources.
This count is of the report-definition objects, not just data charts.
A PBIX is a binary, Windows-authored delivery; a matching `.pbip` source folder
and four CSV input tables are included in the release handoff.

## Five-day aggregate snapshot

| Slice | Groups | Requests | Marked closed |
|---|---:|---:|---:|
| By day | 5 | 50,740 | 47,101 |
| By agency | 14 | 50,740 | 47,101 |
| By borough | 6 | 50,740 | 47,101 |
| Top-15 complaints | 15 | 30,763 | 30,323 |

- Not closed: **3,639**; closed / all created-window requests = **92.83%**.
- Top-15 complaint coverage: **60.63%** of requests (30,763 / 50,740).
- Other complaint categories outside the Top 15: **19,977** requests.
- Closed figures are snapshot statuses of requests **created** in the period, not
  events closed on the plotted date; the ratio is **not a service SLA**.
- Empty agency median values are missing, not zero; a median of medians is not the
  global request-grain median.

## Verification status (separate forms of evidence)

- **Validated here:** PBIX ZIP CRC, machine-readable JSON, five page definitions,
  embedded semantic model presence, five background assets, 86 visuals, and four
  source CSV aggregate reconciliations. SHA-256: `f7e42a731065facc6595c2daecf64bdac7f7b9f87b01ddf3eeef541bee05c286`.
- **Owner reported:** Windows Power BI Desktop opens five pages, data shown, and
  saved the final `.pbix`; dark-frame page transition was acceptable.
- **Not independently executed here:** Power BI Desktop GUI render, a real-time
  source refresh, PBIX DataModel semantic equivalence to every CSV row, a full
  PostgreSQL end-to-end refresh, production/service monitoring, or scheduler SLA.

## Reproducible and safe workflow

1. Install the matching release payload in the repository under `powerbi/native/`.
2. Open its `DataForge360_Cinematic_v5.1.pbix` in Power BI Desktop.
3. If refreshing from CSV, run `powerbi/native/source/DataForge360_PowerBI/SET_DATA_PATHS.ps1`
   in its directory and open `project.pbip`. Then Refresh.
4. Run `python powerbi/validate_demo_exports.py` to validate exported aggregate
   totals in the original GitHub `powerbi/demo_exports/` folder.
5. Create actual Desktop screenshots after verifying values. Never substitute an
   AI-generated mockup or a decorative static background for a real screenshot.
6. Review PBIX embedded data/source connections before public distribution.

## Model caveat

This native report uses **four independent aggregate CSV tables**. It is *not*
the same model as the PostgreSQL `analytics_marts` dbt star schema. Therefore
cross-filtering across agency, borough, complaint and daily aggregates would
not be statistically valid. Rebuild the report on request-grain marts for true
cross-filtering and production-grade incremental refresh.

See [Power BI model guide](POWER_BI.md), [snapshot build guide](../powerbi/BUILD_SNAPSHOT_REPORT.md),
and [pipeline architecture](ARCHITECTURE.md).
