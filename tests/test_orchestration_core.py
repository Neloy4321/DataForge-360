"""Offline unit tests: no Prefect server, NYC API or database required."""

import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from dataforge.orchestration_core import (
    DEFAULT_DAILY_RECORD_CAP, IncompleteWindowError, build_analytics,
    historical_daily_windows, new_report,
    previous_complete_days,
    require_complete_snapshot, require_database_environment, validate_window,
    write_evidence,
)


class OrchestrationCoreTests(unittest.TestCase):
    def test_reconciliation_windows_are_daily_and_oldest_first(self):
        self.assertEqual(previous_complete_days(lookback_days=3, today=date(2026, 9, 5)), [
            (date(2026, 9, 2), date(2026, 9, 3)),
            (date(2026, 9, 3), date(2026, 9, 4)),
            (date(2026, 9, 4), date(2026, 9, 5)),
        ])

    def test_unbounded_reconciliation_is_rejected(self):
        with self.assertRaises(ValueError):
            previous_complete_days(lookback_days=8)

    def test_default_daily_cap_covers_observed_real_partition_peak(self):
        # Owner-provided Sept 2026 logs included a 10,842-row day.
        self.assertGreater(DEFAULT_DAILY_RECORD_CAP, 10842)
        self.assertLessEqual(DEFAULT_DAILY_RECORD_CAP, 1_000_000)

    def test_window_and_caps_are_validated(self):
        with self.assertRaises(ValueError):
            validate_window(date(2026, 9, 2), date(2026, 9, 1), 100, 50)
        with self.assertRaises(ValueError):
            validate_window(date(2026, 9, 1), date(2026, 9, 2), 0, 50)
        with self.assertRaises(ValueError):
            validate_window(date(2026, 9, 1), date(2026, 9, 2), 100, 0)
        # Keep Prefect preflight in lock-step with the source client.
        validate_window(date(2026, 9, 1), date(2026, 9, 2), 100, 5000)
        with self.assertRaises(ValueError):
            validate_window(date(2026, 9, 1), date(2026, 9, 2), 100, 5001)

    def test_historical_backfill_is_daily_oldest_first_and_exclusive_end(self):
        self.assertEqual(historical_daily_windows(date(2026, 9, 1), date(2026, 9, 3)), [
            (date(2026, 9, 1), date(2026, 9, 2)),
            (date(2026, 9, 2), date(2026, 9, 3)),
        ])

    def test_historical_backfill_refuses_empty_reversed_or_long_ranges(self):
        for start, end in [
            (date(2026, 9, 1), date(2026, 9, 1)),
            (date(2026, 9, 2), date(2026, 9, 1)),
            (date(2026, 9, 1), date(2026, 10, 3)),
        ]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                historical_daily_windows(start, end)
        self.assertEqual(len(historical_daily_windows(date(2026, 9, 1),
                                                     date(2026, 10, 2))), 31)

    def test_cap_guard_prevents_silent_truncation(self):
        capped = {"dataset_id": "erm2-nwe9", "reached_max_records": True}
        with self.assertRaises(IncompleteWindowError):
            require_complete_snapshot(capped, allow_truncated=False)
        require_complete_snapshot(capped, allow_truncated=True)
        require_complete_snapshot({**capped, "reached_max_records": False},
                                  allow_truncated=False)

    def test_unconfigured_database_fails_before_ingestion(self):
        with patch.dict(os.environ, {"DATABASE_URL": "", "DBT_PASSWORD": ""}):
            with self.assertRaises(RuntimeError):
                require_database_environment()

    def test_dbt_invocation_checks_summary_and_excludes_credentials_from_args(self):
        observed = {}

        def fake_run(command, **kwargs):
            observed.update(command=command, kwargs=kwargs)
            return SimpleNamespace(returncode=0, stdout=(
                "Done. PASS=38 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=38"))

        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://not-secret:abc@localhost/db",
                                  "DBT_PASSWORD": "never-publish-this"}):
            result = build_analytics(executable="dbt-test-exe", runner=fake_run)
        self.assertEqual((result["passed"], result["total"]), (38, 38))
        self.assertEqual(observed["command"][0:2], ["dbt-test-exe", "build"])
        self.assertNotIn("never-publish-this", " ".join(observed["command"]))
        self.assertNotIn("abc@localhost", " ".join(observed["command"]))
        self.assertEqual(observed["kwargs"]["env"]["DBT_ENGINE_MANAGE_STATE"], "0")

    def test_dbt_does_not_claim_success_without_test_summary(self):
        def fake_run(command, **kwargs):
            return SimpleNamespace(returncode=0, stdout="Something succeeded")

        with patch.dict(os.environ, {"DATABASE_URL": "local", "DBT_PASSWORD": "local"}):
            with self.assertRaises(RuntimeError):
                build_analytics(executable="dbt-test", runner=fake_run)

    def test_atomic_evidence_contains_no_credentials(self):
        report = new_report(date(2026, 9, 1), date(2026, 9, 2),
                            max_records=100, allow_truncated=True)
        report["status"] = "succeeded"
        with tempfile.TemporaryDirectory() as temp:
            path = write_evidence(report, Path(temp))
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["status"],
                             "succeeded")
            self.assertFalse(list(Path(temp).glob("*.partial")))
            self.assertNotIn("DATABASE_URL", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

