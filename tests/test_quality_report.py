"""Offline structural/data-quality checks, with no database dependency."""

import unittest
from datetime import date

from dataforge.quality_report import STAGING_SQL, build_quality_report, fact_daily_sql


class QualityReportTests(unittest.TestCase):
    def setUp(self):
        self.start = date(2026, 9, 1)
        self.end = date(2026, 9, 3)
        self.staging = [
            {"day": self.start, "rows": 2, "missing_agency": 1,
             "missing_complaint": 0, "missing_borough": 0, "missing_status": 0,
             "closed_without_timestamp": 1, "negative_close_interval": 0},
            {"day": date(2026, 9, 2), "rows": 3, "missing_agency": 0,
             "missing_complaint": 0, "missing_borough": 1, "missing_status": 0,
             "closed_without_timestamp": 0, "negative_close_interval": 1},
        ]
        self.facts = [
            {"day": self.start, "rows": 2, "distinct_ids": 2,
             "valid_resolution_count": 1},
            {"day": date(2026, 9, 2), "rows": 3, "distinct_ids": 3,
             "valid_resolution_count": 2},
        ]

    def fake_fetch(self, _dsn, query, parameters):
        self.assertEqual(parameters, (self.start, self.end))
        return self.staging if query == STAGING_SQL else self.facts

    def test_two_days_pass_and_warnings_are_not_silenced(self):
        report = build_quality_report("private-dsn", self.start, self.end,
                                      fetch=self.fake_fetch)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["days_checked"], 2)
        self.assertEqual(report["staging_rows"], 5)
        self.assertEqual(report["fact_rows"], 5)
        self.assertEqual(report["days"][0]["source_quality_observations"][
            "closed_without_timestamp"], 1)
        self.assertEqual(report["days"][1]["source_quality_observations"][
            "negative_close_interval"], 1)
        self.assertNotIn("private-dsn", str(report))

    def test_structural_mismatch_fails_with_exact_day(self):
        self.facts[1]["rows"] = 2
        report = build_quality_report("dsn", self.start, self.end,
                                      fetch=self.fake_fetch)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["failed_days"], ["2026-09-02"])

    def test_missing_day_fails_and_does_not_invent_rows(self):
        self.staging = self.staging[:1]
        self.facts = self.facts[:1]
        report = build_quality_report("dsn", self.start, self.end,
                                      fetch=self.fake_fetch)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["days"][1]["staging_rows"], 0)

    def test_invalid_sql_identifier_rejected(self):
        with self.assertRaises(ValueError):
            fact_daily_sql("analytics; DROP TABLE x; --")
        with self.assertRaises(ValueError):
            build_quality_report("dsn", self.start, self.end,
                                 prefix="analytics; --", fetch=self.fake_fetch)

    def test_more_than_31_days_rejected(self):
        with self.assertRaises(ValueError):
            build_quality_report("dsn", date(2026, 9, 1), date(2026, 10, 3),
                                 fetch=self.fake_fetch)


if __name__ == "__main__":
    unittest.main()
