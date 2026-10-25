# DataForge / 360 — Cinematic Final Polish (native PBIP)

This is an **editable Power BI project**, not a screenshot. All cards, charts and DAX measures remain native. Cinematic skyline, dark panel backdrops and decorative icons are page-background images. No static values are painted into those backgrounds.

## Open on Windows
1. Extract the full ZIP into a simple folder such as `C:\DataForge360_Final` (avoid an old previously extracted project).
2. Open Windows PowerShell in the `DataForge360_PowerBI` subfolder.
3. Run `powershell -NoProfile -ExecutionPolicy Bypass -File .\SET_DATA_PATHS.ps1`. The script updates the four CSV paths for **this extracted folder only**.
4. Double-click `project.pbip`, then in Power BI Desktop choose Home > Refresh and View > Page view > Fit to page.
5. Confirm the five report pages, charts, values and refreshed rows; File > Save As > PBIX to save a self-contained native desktop report.

## Data scope, validation & important caveats
- Source: user-provided NYC 311 aggregate CSV snapshot, created Sep 1–5, 2026. This is **not** an official NYC government dashboard or a live feed.
- Daily, agency and borough totals independently reconcile to 50,740 requests and 47,101 requests later marked closed. Remaining 3,639 requests are **not closed**, not necessarily 'Open'.
- Top 15 complaints total 30,763 requests and 30,323 closed. These complaint categories represent 60.63% of all requests; do not add rollups across four tables.
- The line chart shows requests **created** by each date, with later closure status as of the extract; not actual closure-date volumes.
- Medians are per-group summaries; do not average medians or interpret all group medians as global medians.
- The report includes live Power BI visuals and static visual-design backgrounds. Cards/graphs react to the dataset; decorative design components do not.
- Power BI Desktop cannot be opened or fully rendered on this Linux build host. JSON/field/reference/data reconciliation is verified; final visual rendering/Refresh acceptance must be completed in Power BI Desktop.

## Note
The page-background PNGs are registered PBIR resources and must remain alongside the report. Do not extract only `project.pbip` without its semantic model, report definition, and data directory.
