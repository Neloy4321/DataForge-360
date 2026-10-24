"""Regression acceptance: daily charts display dates, never noon tick marks."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dataforge.dashboard_app import build_daily_trend_chart


def main() -> None:
    sample = [
        {"day": date(2026, 9, 1), "requests": 9903, "closed_requests": 9200},
        {"day": date(2026, 9, 2), "requests": 10163, "closed_requests": 9315},
        {"day": date(2026, 9, 3), "requests": 10842, "closed_requests": 10000},
        {"day": date(2026, 9, 4), "requests": 10527, "closed_requests": 9900},
        {"day": date(2026, 9, 5), "requests": 9305, "closed_requests": 8686},
    ]
    chart = build_daily_trend_chart(sample)
    assert chart is not None
    encoding = chart.to_dict()["encoding"]
    assert encoding["x"]["field"] == "day_label", encoding
    assert encoding["x"]["type"] == "ordinal", encoding
    assert encoding["x"]["sort"] == "ascending", encoding
    expected = [day["day"].isoformat() for day in sample]
    assert chart.data["day_label"].tolist() == expected + expected
    assert chart.data["metric"].tolist() == ["requests"] * 5 + ["closed_requests"] * 5
    assert build_daily_trend_chart([]) is None
    print("PASS: categorical daily x-axis, correct ordering and empty-data fallback")


if __name__ == "__main__":
    main()
