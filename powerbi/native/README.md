# DataForge 360 — native Power BI delivery (V5.1)

This folder contains the **Power BI Desktop-saved file** `DataForge360_Cinematic_v5.1.pbix`
and the matching editable Power BI project under `source/DataForge360_PowerBI/`.

- Final PBIX SHA-256: `f7e42a731065facc6595c2daecf64bdac7f7b9f87b01ddf3eeef541bee05c286`
- Five report pages and 86 native visuals (validated from the PBIX internal report definition)
- Four separate imported aggregate CSVs for 2026-09-01 through 2026-09-05.
- See `release_manifest.json` for counts, assets and static validation results.

## Open the deliverable

Open `DataForge360_Cinematic_v5.1.pbix` on **Windows Power BI Desktop**.
The PBIX is self-contained for displaying its saved aggregate snapshot, but a refresh
may still require the original CSV paths, depending on the Desktop data-source settings.

For an editable/reproducible **PBIP** copy, open a PowerShell terminal in
`source/DataForge360_PowerBI/` and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\SET_DATA_PATHS.ps1'
Invoke-Item -LiteralPath '.\project.pbip'
```

Then Refresh and review the five pages in Desktop. The script uses the CSV files
bundled under `source/DataForge360_PowerBI/data/`. When moving folders, rerun the
script; do not commit a machine-specific updated TMDL path.

## Accurate interpretation

The report represents a **historical, non-live snapshot of requests created during
September 1–5, 2026**. A Closed count means *status observed later* for records
created in that period; it does not count closure events that occurred on each day.
Not Closed includes all non-Closed statuses and is not synonymous with Open.

The four CSVs are independent aggregated views of the same requests. They must
not be joined or summed together as though they were request-grain records.
A Top-15 complaint total covers only 30,763 of the 50,740 requests.

**Distribution caution:** Power BI files can embed data and local-source metadata.
Before changing the GitHub repo from private to public, review the embedded data,
all source paths, screenshots and license/provenance. This is an independent portfolio
visualization, not a NYC-endorsed service or a citywide comprehensive audit.
