"""Static integrity test for the optional native Power BI V5.1 release.

Not a substitute for Power BI Desktop rendering, semantic model testing or live refresh.
"""
import csv
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent / "native"
REPORT = ROOT / "DataForge360_Cinematic_v5.1.pbix"
MANIFEST = ROOT / "release_manifest.json"
CSV_DIR = ROOT / "source" / "DataForge360_PowerBI" / "data"
SUFFIX = "2026-09-01_2026-09-05"
EXPECTED = {
    "daily": (5, 50740, 47101),
    "agency": (14, 50740, 47101),
    "borough": (6, 50740, 47101),
    "complaint": (15, 30763, 30323),
}
PAGES = (
    "Executive Overview", "Agency Performance", "Borough Analytics",
    "Complaint Intelligence", "Data Quality & Method",
)


def validate():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    digest = hashlib.sha256(REPORT.read_bytes()).hexdigest()
    if digest != manifest["pbix_sha256"]:
        raise ValueError("PBIX SHA-256 mismatches original release manifest")
    if not zipfile.is_zipfile(REPORT):
        raise ValueError("PBIX is not a readable zip-compatible package")
    with zipfile.ZipFile(REPORT) as archive:
        if archive.testzip() is not None:
            raise ValueError("PBIX ZIP integrity error")
        names = set(archive.namelist())
        if "DataModel" not in names:
            raise ValueError("No embedded DataModel")
        ids = json.loads(archive.read("Report/definition/pages/pages.json"))["pageOrder"]
        pages = []
        total_visuals = 0
        for pid in ids:
            prefix = f"Report/definition/pages/{pid}/"
            pages.append(json.loads(archive.read(prefix + "page.json"))["displayName"])
            visuals = [n for n in names if n.startswith(prefix + "visuals/")
                       and n.endswith("/visual.json")]
            total_visuals += len(visuals)
            for filename in visuals:
                json.loads(archive.read(filename))
        if tuple(pages) != PAGES:
            raise ValueError("Unexpected Power BI report page titles/order")
        if total_visuals != manifest["visual_count"]:
            raise ValueError("Unexpected report visual count")
        backgrounds = [n for n in names if
                       "Report/StaticResources/RegisteredResources/DataForgeCinematic-" in n
                       and n.endswith(".png")]
        if len(backgrounds) != 5:
            raise ValueError("Unexpected number of decorative backgrounds")
    for kind, expected in EXPECTED.items():
        csv_path = CSV_DIR / f"dataforge_{kind}_{SUFFIX}.csv"
        with csv_path.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        found = (len(rows), sum(int(x["requests"]) for x in rows),
                 sum(int(x["closed_requests"]) for x in rows))
        if found != expected:
            raise ValueError(f"{kind}: aggregate reconciliation failed: {found}")
    return {"status": "passed", "pages": list(PAGES),
            "visual_count": total_visuals, "pbix_sha256": digest,
            "limits": "Static artifacts only; not a Desktop or live refresh test"}


if __name__ == "__main__":
    try:
        print(json.dumps(validate(), indent=2))
    except (ValueError, OSError, KeyError, json.JSONDecodeError, zipfile.BadZipFile) as err:
        print(json.dumps({"status": "failed", "error": str(err)}))
        raise SystemExit(1)
