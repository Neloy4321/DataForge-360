"""Render the actual Streamlit app against isolated synthetic CI analytics."""

from __future__ import annotations

import os
from pathlib import Path


def main() -> None:
    from streamlit.testing.v1 import AppTest

    dsn = os.environ.get("DATAFORGE_TEST_DATABASE_URL", "")
    if not dsn or "dataforge_ci" not in dsn:
        raise RuntimeError("Streamlit smoke requires an isolated CI database")
    os.environ["DATABASE_URL"] = dsn
    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "dataforge" / "dashboard_app.py"),
        default_timeout=60,
    ).run()
    if app.exception:
        raise AssertionError(f"Dashboard runtime errors: {[str(x.message) for x in app.exception]}")
    assert len(app.metric) == 4, "Expected four live KPI cards"
    assert app.metric[0].value == "4", "Dashboard must show four fixture requests"
    print("PASS: interactive Streamlit app loads real mart data without runtime errors")


if __name__ == "__main__":
    main()
