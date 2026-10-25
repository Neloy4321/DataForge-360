"""Fail-closed static validation of Power BI PBIX, PBIP report source and CSVs.

Checks full report-definition/asset parity against the owner-saved PBIX.
Does NOT execute Windows Power BI Desktop, establish TMDL/DataModel equivalence,
perform real PostgreSQL refresh, or certify production deployment.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import zipfile

EXPECTED_PAGE_NAMES = (
    "Executive Overview", "Agency Performance", "Borough Analytics",
    "Complaint Intelligence", "Data Quality & Method",
)
EXPECTED_COUNTS = {
    "daily": (5, 50_740, 47_101),
    "agency": (14, 50_740, 47_101),
    "borough": (6, 50_740, 47_101),
    "complaint": (15, 30_763, 30_323),
}
DATE_SPAN = "2026-09-01_2026-09-05"
DEFAULT_ROOT = Path(__file__).resolve().parent / "native"
DEFAULT_PROJECT = DEFAULT_ROOT / "source" / "DataForge360_PowerBI"
PBIX_REPORT_PREFIXES = ("Report/definition/", "Report/StaticResources/")


def _verify_aggregate_csvs(data_dir: Path) -> dict[str, dict[str, int]]:
    stats: dict[str, dict[str, int]] = {}
    for kind, expected in EXPECTED_COUNTS.items():
        path = data_dir / f"dataforge_{kind}_{DATE_SPAN}.csv"
        with path.open("r", newline="", encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        fields = ["day", "requests", "closed_requests"] if kind == "daily" else [
            "label", "requests", "closed_requests", "median_resolution_hours"
        ]
        if not rows or list(rows[0].keys()) != fields:
            raise ValueError(f"Invalid CSV schema: {path}")
        result = (len(rows), sum(int(row["requests"]) for row in rows),
                  sum(int(row["closed_requests"]) for row in rows))
        if result != expected:
            raise ValueError(f"Wrong aggregate totals for {kind}: {result} != {expected}")
        stats[kind] = dict(zip(("rows", "requests", "closed"), result))
    return stats


def verify_pbip_report_parity(archive: zipfile.ZipFile, project_dir: Path) -> dict:
    """Require an equivalent file for every saved-PBIX report definition and resource.

    This is a *static* report-definition comparison only. Power BI Desktop is
    required to confirm a PBIP opens and its semantic model is operational.
    """
    report_dir = project_dir / "project.Report"
    if not (project_dir / "project.pbip").is_file():
        raise ValueError("Editable PBIP entrypoint is missing")
    pbir = report_dir / "definition.pbir"
    if not pbir.is_file():
        raise ValueError("PBIR report entrypoint is missing")
    settings = json.loads(pbir.read_text(encoding="utf-8-sig"))
    if float(settings.get("version", 0)) < 4.0:
        raise ValueError("PBIR report format version must support enhanced definitions")
    if not (project_dir / "project.SemanticModel" / "definition.pbism").is_file():
        raise ValueError("PBIP semantic model entrypoint is missing")

    listed = {p for p in archive.namelist() if p.startswith(PBIX_REPORT_PREFIXES)
              and not p.endswith("/")}
    if not listed:
        raise ValueError("PBIX is missing report definition files")
    for name in sorted(listed):
        relative = name.removeprefix("Report/")
        dest = report_dir / relative
        if not dest.is_file():
            raise ValueError(f"Editable PBIP report source missing: {relative}")
        stored = archive.read(name)
        current = dest.read_bytes()
        if name.endswith(".json"):
            try:
                equal = json.loads(stored) == json.loads(current)
            except (UnicodeDecodeError, ValueError) as exc:
                raise ValueError(f"Unparseable PBIP source JSON: {relative}") from exc
        else:
            equal = stored == current
        if not equal:
            raise ValueError(f"PBIP source differs from saved PBIX: {relative}")

    expected_visuals = {n.removeprefix("Report/") for n in listed
                        if n.endswith("/visual.json")}
    actual_visuals = {p.relative_to(report_dir).as_posix()
                      for p in report_dir.rglob("visual.json")}
    if actual_visuals != expected_visuals:
        raise ValueError("PBIP visual file set does not match PBIX")
    registered = [n for n in listed if "/RegisteredResources/" in n]
    # Every resource declared by the PBIX must be checked above, including theme.
    return {
        "status": "passed",
        "source_report_files": len(listed),
        "source_visuals": len(expected_visuals),
        "registered_resource_files": len(registered),
        "scope": "PBIX report JSON semantics / resource byte parity only; Windows reopen and TMDL model equivalence not checked",
    }


def validate(report: Path, manifest: Path, data_dir: Path,
             project_dir: Path = DEFAULT_PROJECT) -> dict:
    expected = json.loads(manifest.read_text(encoding="utf-8"))
    actual_hash = hashlib.sha256(report.read_bytes()).hexdigest()
    if actual_hash != expected["pbix_sha256"]:
        raise ValueError("PBIX checksum does not match release manifest")
    if not zipfile.is_zipfile(report):
        raise ValueError("Not a zip-compatible Power BI report")
    with zipfile.ZipFile(report) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"Invalid PBIX CRC entry: {bad}")
        names = set(archive.namelist())
        if "DataModel" not in names:
            raise ValueError("PBIX embedded semantic model missing")
        page_order = json.loads(archive.read("Report/definition/pages/pages.json"))["pageOrder"]
        visual_total = 0
        page_names: list[str] = []
        for page_id in page_order:
            base = f"Report/definition/pages/{page_id}/"
            page = json.loads(archive.read(base + "page.json"))
            page_names.append(page["displayName"])
            visuals = [n for n in names if n.startswith(base + "visuals/")
                       and n.endswith("/visual.json")]
            visual_total += len(visuals)
            for visual in visuals:
                json.loads(archive.read(visual))
        if tuple(page_names) != EXPECTED_PAGE_NAMES:
            raise ValueError(f"Unexpected page list: {page_names}")
        if visual_total != expected["visual_count"]:
            raise ValueError("Report visual count changed")
        backgrounds = [n for n in names if n.startswith(
            "Report/StaticResources/RegisteredResources/DataForgeCinematic-")
            and n.endswith(".png")]
        if len(backgrounds) != expected["cinematic_background_assets"]:
            raise ValueError("Wrong number of cinematic assets")
        pbip = verify_pbip_report_parity(archive, project_dir)
    stats = _verify_aggregate_csvs(data_dir)
    return {
        "status": "passed",
        "sha256": actual_hash,
        "pages": page_names,
        "visuals": visual_total,
        "sources": stats,
        "editable_pbip_report_parity": pbip,
        "limits": "Static artifact parity only; independent Windows PBIP reopen / semantic model reconstruction and live data validation not executed",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path,
                        default=DEFAULT_ROOT / "DataForge360_Cinematic_v5.1.pbix")
    parser.add_argument("--manifest", type=Path,
                        default=DEFAULT_ROOT / "release_manifest.json")
    parser.add_argument("--csv-dir", type=Path,
                        default=DEFAULT_PROJECT / "data")
    parser.add_argument("--project-dir", type=Path, default=DEFAULT_PROJECT)
    args = parser.parse_args()
    try:
        print(json.dumps(validate(args.report, args.manifest, args.csv_dir,
                                  args.project_dir), indent=2))
        return 0
    except (ValueError, TypeError, KeyError, OSError, json.JSONDecodeError,
            zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
