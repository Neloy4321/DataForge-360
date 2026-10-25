# DataForge 360 — native cinematic Power BI V5.1

**Status (2026-10-25):** The project owner provided a Power BI Desktop-saved `.pbix` after opening and saving the cinematic five-page report on Windows. The binary file is included in the separate handoff package; it has **not yet been committed to this repository**. Do not mistake this page for proof of repository binary delivery or fresh Windows automation.

## Artifact inspection

- Original owner-provided PBIX: `project.pbix`, 684,602 bytes.
- SHA-256: `f7e42a731065facc6595c2daecf64bdac7f7b9f87b01ddf3eeef541bee05c286`.
- PBIX container integrity/ZIP CRC: PASS.
- Five report pages: Executive Overview, Agency Performance, Borough Analytics, Complaint Intelligence, Data Quality & Method.
- 86 native report-definition visual objects; five decorative cinematic background images.
- Embedded semantic model detected. All parseable report JSON files parsed successfully.

The owner reported working Windows Power BI pages and a saved PBIX. The visual renderer, subsequent refresh, and full embedded model semantics were **not independently executed here**.

## Snapshot reconciliation

| Aggregate view | Rows | Requests | Marked closed |
|---|---:|---:|---:|
| Daily | 5 | 50,740 | 47,101 |
| Agency | 14 | 50,740 | 47,101 |
| Borough | 6 | 50,740 | 47,101 |
| Complaint (Top 15) | 15 | 30,763 | 30,323 |

- Not closed: 3,639; close-out status ratio: 92.83%.
- Top-15 coverage: 30,763 / 50,740 = approximately 60.63%; the other 19,977 requests are not represented by the Top-15 complaint table.
- These dates are **created dates** (September 1–5, 2026); marked-closed counts are the status of those records at the snapshot, **not closure events on each plotted date**.
- The ratios are not a service SLA. This is an independent, non-live portfolio visualization, not an NYC-affiliated government report.

## Model and distribution cautions

The native report is based on four independent **aggregate CSV tables**. It is not the request-grain PostgreSQL/dbt star schema described in [POWER_BI.md](POWER_BI.md). Do not join or sum the rollups or imply cross-filtering one category filters another correctly. Median resolution hours are per-group statistics, not a global median. A missing median is not zero.

PBIX files embed data and can retain local data-source paths. Review content, metadata, licenses and source connections before publishing an unreviewed file to a public repository.

## Local release installation

The user-specific handoff bundle contains the native PBIX and its editable matching PBIP project, an offline CSV input copy and an installer to copy them under `powerbi/native/`. Its installer checks the PBIX checksum and **does not auto-commit or push**. After installing and verifying locally, commit the binary and source with the authenticated Git client.

Capture real Power BI Desktop screenshots from the final report after opening it; do not use AI mockups or decorative background files as screenshot evidence.

See [Power BI snapshot guide](../powerbi/BUILD_SNAPSHOT_REPORT.md) and [Power BI modeling guide](POWER_BI.md).