"""Audit four aggregate NYC 311 CSV exports for an offline Power BI report.

Standard library only; checks the export contract, not source completeness.
"""

import argparse
import csv
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


KIND = ("daily", "agency", "borough", "complaint")
DETAIL_FIELDS = ("label", "requests", "closed_requests", "median_resolution_hours")
DAILY_FIELDS = ("day", "requests", "closed_requests")


def _count(value, path, line):
    if not value.isdigit():
        raise ValueError(f"{path}:{line}: invalid nonnegative count {value!r}")
    return int(value)


def _load(path, kind):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != (DAILY_FIELDS if kind == "daily" else DETAIL_FIELDS):
            raise ValueError(f"{path}: invalid header")
        rows, seen, previous = [], set(), None
        for index, data in enumerate(reader, start=2):
            if None in data or any(v is None for v in data.values()):
                raise ValueError(f"{path}:{index}: malformed row")
            key = data["day" if kind == "daily" else "label"]
            if not key or not key.strip() or key in seen:
                raise ValueError(f"{path}:{index}: empty or duplicate key {key!r}")
            seen.add(key)
            if kind == "daily":
                try:
                    date.fromisoformat(key)
                except ValueError as error:
                    raise ValueError(f"{path}:{index}: bad ISO date") from error
            elif key[0] in "=+@":
                raise ValueError(f"{path}:{index}: unsafe formula prefix")
            requested = _count(data["requests"], path, index)
            closed = _count(data["closed_requests"], path, index)
            if closed > requested:
                raise ValueError(f"{path}:{index}: closed exceeds requests")
            if kind != "daily":
                if previous is not None and requested > previous:
                    raise ValueError(f"{path}:{index}: requests not descending")
                previous = requested
                if data["median_resolution_hours"]:
                    try:
                        median = Decimal(data["median_resolution_hours"])
                    except InvalidOperation as error:
                        raise ValueError(f"{path}:{index}: invalid median") from error
                    if not median.is_finite() or median < 0:
                        raise ValueError(f"{path}:{index}: invalid median")
            rows.append((key, requested, closed))
    if not rows:
        raise ValueError(f"{path}: no rows")
    if kind == "daily" and [r[0] for r in rows] != sorted(r[0] for r in rows):
        raise ValueError(f"{path}: dates not ascending")
    if kind == "complaint" and len(rows) > 15:
        raise ValueError(f"{path}: expected at most 15 top complaints")
    return rows


def validate(directory, snapshot):
    counts = {}
    for kind in KIND:
        rows = _load(directory / f"dataforge_{kind}_{snapshot}.csv", kind)
        counts[kind] = {
            "groups": len(rows),
            "requests": sum(r[1] for r in rows),
            "closed_requests": sum(r[2] for r in rows),
        }
    base = counts["daily"]
    if base["requests"] == 0:
        raise ValueError("no requests in daily window")
    for kind in ("agency", "borough"):
        if (counts[kind]["requests"], counts[kind]["closed_requests"]) != (
            base["requests"], base["closed_requests"]
        ):
            raise ValueError(f"{kind}: totals disagree with daily")
    top = counts["complaint"]
    if top["requests"] > base["requests"] or top["closed_requests"] > base["closed_requests"]:
        raise ValueError("complaint top 15 exceeds full-window totals")
    return {
        "status": "passed",
        "snapshot": snapshot,
        "exports": counts,
        "closure_rate": round(base["closed_requests"] / base["requests"], 6),
        "other_complaint_requests": base["requests"] - top["requests"],
        "top15_coverage": round(top["requests"] / base["requests"], 6),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path(__file__).parent / "demo_exports")
    parser.add_argument("--snapshot", default="2026-09-01_2026-09-05")
    options = parser.parse_args()
    try:
        print(json.dumps(validate(options.directory, options.snapshot), indent=2))
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
