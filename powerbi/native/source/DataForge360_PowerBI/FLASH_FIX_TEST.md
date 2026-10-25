# DataForge / 360 — Page-switch white-flash mitigation (V5.1)

This is a **testable mitigation**, not a guarantee of eliminating a Power BI Desktop renderer flash. The original cinematic report and all its data-bound visuals remain intact.

## Exactly what changed
- Added explicit opaque deep-navy `#061525` **canvas fallback color** to each of the five existing background-image page definitions.
- Added opaque deep-navy **wallpaper (`outspace`)** to each of the five pages.
- No chart, measure, source CSV, page layout or image resource was modified.

## Test without breaking V5
1. Close the old report first. Extract this ZIP to a new folder, not over V5.
2. In the extracted `DataForge360_PowerBI` directory run `powershell -NoProfile -ExecutionPolicy Bypass -File .\SET_DATA_PATHS.ps1`.
3. Open `project.pbip`, use Refresh and View > Page view > Fit to page.
4. Navigate rapidly Executive -> Agency -> Borough -> Complaint -> Data Quality, then backwards. Compare with the old V5 on the same machine.
5. If there is still a white intermediate frame, Power BI Desktop may be clearing/repainting its report surface before applying page styling. This cannot be reliably eliminated with page-background JSON; measure/report performance optimization or a different presentation environment may be needed.

Do not change the existing V5, and do not claim the change is confirmed until actual Windows Power BI Desktop testing.
