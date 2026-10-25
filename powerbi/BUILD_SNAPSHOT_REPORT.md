# DataForge 360 — Power BI snapshot report

This starter pack builds an **offline, aggregate-only Power BI Desktop report** from the four NYC 311 CSV exports for **2026-09-01 through 2026-09-05**. It is a reproducible showcase dataset, not a live-connected `.pbix` and not a complete NYC 311 historical dataset.

## 1. Import the data in Power BI Desktop

1. Pull this repository on your Windows machine. In **Power BI Desktop**, use **Home → Get data → Text/CSV** for each file in `powerbi/demo_exports/`.
2. Select **Transform data** and set types as below. Then select **Close & Apply**.

| CSV prefix | Rename table | Types |
| --- | --- | --- |
| `dataforge_daily_` | `Daily` | `day` Date, `requests` Whole number, `closed_requests` Whole number |
| `dataforge_agency_` | `Agency` | `label` Text, two counts Whole number, `median_resolution_hours` Decimal number |
| `dataforge_borough_` | `Borough` | Same as Agency |
| `dataforge_complaint_` | `Complaint` | Same as Agency |

3. In **Model view**, ensure there are **no relationships between these four tables**. They are *independent aggregations of the same requests*. Delete any automatically inferred relationship.
4. Optionally use **Design → Import theme** to apply `powerbi/dataforge_theme.json` (ribbon location can vary by Desktop version).
5. Create each measure in `powerbi/snapshot_measures.dax` separately via **Modeling → New measure**. The `.dax` text is not auto-imported.

## 2. Suggested pages and visuals

Use 16:9 canvas and show **“NYC 311 | bounded snapshot | Sep 1–5, 2026”** on each page. Sort ranking bars by requests descending.

| Page | Visual | Fields |
| --- | --- | --- |
| 01 Executive Overview | 4 cards | `[Total Requests]`, `[Closed Requests]`, `[Closure Rate]`, `[Not Closed Requests]` |
| | Line chart | `Daily[day]` (categorical date) vs `Daily[requests]` summed |
| | Borough bar | `Borough[label]` vs `Borough[requests]` summed |
| 02 Agency Performance | Horizontal bar | `Agency[label]` vs `[Agency Requests]` |
| | Detail table | `Agency[label]`, counts, `[Agency Closure Rate]`, median (Don't summarize) |
| 03 Borough Analytics | Bar | `Borough[label]` vs `[Borough Requests]` |
| | Detail table | `Borough[label]`, counts, `[Borough Closure Rate]`, median (Don't summarize) |
| 04 Complaint Intelligence | Top-15 bar | `Complaint[label]` vs `[Top 15 Complaint Requests]` |
| | Detail table | `Complaint[label]`, counts, `[Complaint Closure Rate]`, median (Don't summarize) |
| | Coverage card | `[Top 15 Coverage - Full Snapshot]`, no page filters |
| 05 Quality & Method | Text/cards | Source, window, bounded scope, dbt 38/38 PASS from local runs, structural reconciliation, caveats below |

**Do not link these aggregated tables.** An Agency selection cannot meaningfully filter a Daily or Complaint CSV: the grain does not preserve that detail. For a properly cross-filterable model use the **PostgreSQL dbt star schema** documented in [`docs/POWER_BI.md`](../docs/POWER_BI.md).

## 3. Verified five-day totals

- Requests: **50,740**; closed: **47,101**; not closed: **3,639**; closure: **92.8%** (1 decimal).
- Five daily points; **14** agencies; **6** borough categories including `UNSPECIFIED`.
- **Top 15 complaints**: **30,763 requests = 60.6%** of all requests. Remaining **19,977** requests belong to omitted complaint categories. Never describe Top-15 as all complaints.
- `EDC`: zero closed requests, so its resolution median is blank. Never replace that missing value with zero.
- Group medians cannot be summed or averaged into the citywide median; use the request-grain star schema for that KPI.

Run the standard-library export validator before import or publishing:

```powershell
python powerbi/validate_demo_exports.py
```

This detects structural CSV/reconciliation errors, but cannot certify API/source completeness or a live schedule.

## 4. Native report handoff

The project owner has already saved and committed a cinematic five-page native
`.pbix` to [`powerbi/native/`](native/) (initial commit `4f783f6`);
the matching editable `.pbip` and four aggregate CSVs are also committed.
Static integrity/reconciliation checks passed. Owner-supplied Windows Desktop
screenshots show five report pages and a working Queens borough-selection
interaction; the Refresh dialog showed all four CSV sources loading and
the owner reported no error at completion. See the
[native report verification](../docs/POWER_BI_NATIVE_REPORT.md) and
[local release acceptance](../docs/LOCAL_RELEASE_ACCEPTANCE_2026-10-25.md).
These screenshots do not constitute an independent automated Desktop run.
An imported `.pbix` embeds data: review its contents and remove
machine-specific paths, credentials and sensitive material before public
distribution.

Useful portfolio screenshots: Overview, Agency, Borough, Top-15 Complaint and Quality/Method pages. Label this an independent NYC Open Data project, not a government-affiliated product.

Source: [NYC 311 Service Requests (2020–present)](https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2020-to-Present/erm2-nwe9).
