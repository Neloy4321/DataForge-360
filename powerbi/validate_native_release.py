"""Validate the owner-supplied native Power BI report and aggregate CSVs.

Standard-library only; performs static artifact checks, NOT GUI rendering,
DB model equivalence, source completeness, or live-refresh acceptance.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import zipfile


EXPECTED_PAGE_NAMES = (
    "Executive Overview",
    "Agency Performance",
    "Borough Analytics",
    "Complaint Intelligence",
    "Data Quality & Method",
)
EXPECTED_COUNTS = {
    "daily": (5, 50_740, 47_101),
    "agency": (14, 50_740, 47_101),
    "borough": (6, 50_740, 47_101),
    "complaint": (15, 30_763, 30_323),
}
DATE_SPAN = "2026-09-01_2026-09-05"
DEFAULT_ROOT = Path(__file__).resolve().parent / "native"


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
        result = (len(rows), sum(int(r["requests"]) for r in rows),
                  sum(int(r["closed_requests"]) for r in rows))
        if result != expected:
            raise ValueError(f"Wrong aggregate totals for {kind}: {result} != {expected}")
        stats[kind] = dict(zip(("rows", "requests", "closed"), result))
    return stats


def validate(report: Path, manifest: Path, data_dir: Path) -> dict:
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
        page_names = []
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
    stats = _verify_aggregate_csvs(data_dir)
    return {
        "status": "passed",
        "sha256": actual_hash,
        "pages": page_names,
        "visuals": visual_total,
        "sources": stats,
        "limits": "Static artifacts only; no Windows Power BI rendering or live source verification",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path,
                        default=DEFAULT_ROOT / "DataForge360_Cinematic_v5.1.pbix")
    parser.add_argument("--manifest", type=Path,
                        default=DEFAULT_ROOT / "release_manifest.json")
    parser.add_argument("--csv-dir", type=Path,
                        default=DEFAULT_ROOT / "source" / "DataForge360_PowerBI" / "data")
    args = parser.parse_args()
    try:
        print(json.dumps(validate(args.report, args.manifest, args.csv_dir), indent=2))
        return 0
    except (ValueError, KeyError, OSError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
