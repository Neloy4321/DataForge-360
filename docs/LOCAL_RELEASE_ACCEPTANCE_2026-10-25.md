# DataForge 360 — local release acceptance (2026-10-25)

**Decision: ACCEPTED for local, portfolio/demo use, within the scope below.**

This is a **bounded local engineering and reporting acceptance**, not a production deployment sign-off, independent live-source completeness audit, hosted reliability guarantee, or claim of third-party certification.

## Accepted evidence

| Area | Evidence | Decision |
|---|---|---|
| Python ingestion and PostgreSQL staging | Earlier GitHub CI checks and owner-supplied Windows 100-row warehouse run recorded in the README | Accepted for bounded local workflow |
| dbt analytics | CI build/tests plus owner-supplied Windows 38/38 dbt run on the 100-row smoke data | Accepted for tested scope |
| Prefect orchestration | Earlier isolated CI and owner-supplied Windows Prefect smoke/backfill evidence; five non-capped daily source windows totaling 50,740 rows described in README | Accepted for tested local runs, **not** unattended scheduler SLA |
| Streamlit dashboard | GitHub CI SQL/UI checks and prior owner-supplied Windows screenshots of Activity, Operations and aggregate map | Accepted for local dashboard scope |
| Power BI native binary | `powerbi/native/DataForge360_Cinematic_v5.1.pbix` committed to `main` as part of `4f783f6`; SHA-256 `f7e42a731065facc6595c2daecf64bdac7f7b9f87b01ddf3eeef541bee05c286` | PASS — committed and structurally checked |
| Power BI five pages | Owner-supplied Windows Desktop screenshots: Executive Overview; Agency Performance; Borough Analytics (clean replacement); Complaint Intelligence; Data Quality & Method. Reviewed for visible layout, readable values and no obvious broken chart or overflow. | PASS — **screenshot-based review**, not an automated renderer test |
| Power BI interaction | Owner-supplied before/after Borough Analytics screenshots show selecting **Queens**, highlighting the category and cross-filtering the page KPIs to 12,493 requests / 11,349 marked closed / 90.84%. | PASS — screenshot-evidenced borough interaction |
| Power BI CSV refresh | Owner-supplied refresh-dialog screenshot shows all four input tables (`daily`, `agency`, `borough`, `complaint`) being read; owner confirmed no error after refresh. | PASS — **owner-reported completion**, with screenshot of refresh in progress; not a separately captured completion log |
| Snapshot arithmetic | Four separately aggregated CSV source views reconcile to 50,740 requests / 47,101 marked closed for daily, agency and borough; Top-15 complaint group has 30,763 / 30,323. Validated with `powerbi/validate_native_release.py`. | PASS — static reconciliation |

## Screenshot review details

The Desktop evidence was provided in the owner's 2026-10-25 project review conversation. It includes five primary page captures, one clean Borough Analytics replacement, one Queens selection capture, and one refresh-in-progress dialog capture. All seven original PNG screenshot files are now **committed to GitHub** under [Power BI V5.1 evidence](evidence/powerbi-v5.1/), together with a screenshot SHA-256 manifest and evidence README. Commit `8742148c` introduced these files; GitHub-reported image blob hashes and sizes were checked against the original local bytes. The refresh screenshot is still only an in-progress image, and the reported error-free completion remains the owner's statement.

The CSVs are **four independent pre-aggregated reporting tables**, **not** the request-grain PostgreSQL/dbt star schema. Page-specific borough interactions are demonstrated; valid cross-table filtering across all four aggregates is **not** asserted. The five-day snapshot is **September 1–5, 2026**, created-date cohorts, not live NYC 311 data. Status marked closed may have changed after creation; 92.83% is not an SLA.

## Acceptance boundary and deferred milestone

**Local portfolio/demo release: ACCEPTED.**

**Only planned future milestone: Hosting, benchmarking and full end-to-end acceptance — DEFERRED BY OWNER (no hosting now).** When resumed, it includes hosted deployment/security and uptime evidence, repeatable throughput/load benchmarking, full-source completeness and late-update reconciliation, unattended schedule reliability, and end-to-end API → PostgreSQL → dbt → Prefect → dashboards verification on an agreed nontrivial window.

These future checks are **not failures of the bounded local release**, but also **must not be marked as executed or passed**. The project is not currently certified production-ready or externally hosted.

## Repository references

- [Current README](../README.md)
- [Power BI Desktop evidence and caveats](POWER_BI_NATIVE_REPORT.md)
- [Native release manifest](../powerbi/native/release_manifest.json)
- [Portfolio case study](DATAFORGE_PORTFOLIO_CASE_STUDY.md)

## Subsequent reproducibility audit

A P0 review identified the initial Git commit omitted the PBIP report's visual
JSON definitions and registered assets although the working PBIX contained
them. The editable report source was subsequently populated with all 86 visual
files and six registered assets from the **final** PBIX. An offline verifier
now checks PBIX↔PBIP **report-definition** semantic parity and resource bytes,
with negative unit tests and GitHub CI. This restores static report-source
completeness, but does **not** supersede the prior local acceptance scope:
Windows Desktop opening of the reconstructed `.pbip`, TMDL model equivalence,
warehouse-fed Power BI and end-to-end production operation have not been
independently accepted. Hosting remains deferred at the owner's request.
