"""Pure, offline regression tests for safe dashboard SQL generation."""

import unittest
from datetime import date

from dataforge.analytics import (
    DashboardFilters, aggregate_csv, dimension_options_query, extent_query, fetch_rows,
    marts_schema, metric_query,
)


class AnalyticsQueryTests(unittest.TestCase):
    def setUp(self):
        self.filters = DashboardFilters(date(2026, 9, 1), date(2026, 9, 2))

    def test_fact_schema_is_quoted_and_scoped(self):
        self.assertEqual(marts_schema("analytics_prefect_ci"), '"analytics_prefect_ci_marts"')
        for bad in ("analytics;drop", "analytics.public", "", "1x", "x" * 70):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                marts_schema(bad)

    def test_date_window_must_be_bounded(self):
        with self.assertRaises(ValueError):
            DashboardFilters(date(2026, 9, 2), date(2026, 9, 1))
        with self.assertRaises(ValueError):
            DashboardFilters(date(2020, 1, 1), date(2026, 9, 2))

    def test_filter_count_and_values_rejected(self):
        with self.assertRaises(ValueError):
            DashboardFilters(self.filters.start, self.filters.end, agencies=("X",) * 31)
        with self.assertRaises(ValueError):
            DashboardFilters(self.filters.start, self.filters.end, statuses=("",))
        with self.assertRaises(ValueError):
            DashboardFilters(self.filters.start, self.filters.end, agencies=["DOT"])

    def test_all_queries_use_selected_cte_and_date_parameters(self):
        for metric in ("overview", "daily", "borough", "agency", "complaint", "status", "map"):
            with self.subTest(metric=metric):
                statement, params = metric_query(metric, self.filters)
                self.assertIn('"analytics_marts"."fct_service_requests"', statement)
                self.assertIn("f.created_day BETWEEN %s AND %s", statement)
                self.assertEqual(params, (self.filters.start, self.filters.end))

    def test_filters_are_bound_not_interpolated(self):
        malicious = "DOT'); DROP TABLE staging.service_requests; --"
        filters = DashboardFilters(self.filters.start, self.filters.end,
                                   agencies=(malicious,), boroughs=("BROOKLYN",),
                                   complaints=("Pothole",), statuses=("Closed",))
        statement, params = metric_query("overview", filters)
        self.assertNotIn(malicious, statement)
        self.assertEqual(statement.count("= ANY(%s)"), 4)
        self.assertEqual(params[2], ["BROOKLYN"])
        self.assertEqual(params[3], [malicious])

    def test_map_has_privacy_threshold_and_fixed_limit(self):
        statement, _ = metric_query("map", self.filters)
        self.assertIn("round(latitude::numeric, 2)", statement)
        self.assertIn("HAVING count(*) >= 5", statement)
        self.assertIn("LIMIT 400", statement)
        self.assertNotIn("service_request_id", statement)

    def test_breakdowns_have_stable_top_n_order(self):
        for metric in ("borough", "agency", "complaint", "status"):
            statement, _ = metric_query(metric, self.filters)
            self.assertIn("LIMIT 15", statement)
            self.assertIn("ORDER BY requests DESC, label ASC", statement)

    def test_unsupported_metric_rejected(self):
        with self.assertRaises(ValueError):
            metric_query("source_payload", self.filters)

    def test_dimension_queries_do_not_select_pii(self):
        for metric in ("borough", "agency", "complaint", "status"):
            statement, params = dimension_options_query(metric)
            self.assertIn("LIMIT 500", statement)
            self.assertEqual(params, ())
            self.assertNotIn("incident_address", statement)
        self.assertIn("count(*)", extent_query()[0])

    def test_connection_requires_environment_and_read_only_query(self):
        with self.assertRaises(ValueError):
            fetch_rows("", "SELECT 1")
        with self.assertRaises(ValueError):
            fetch_rows("fake-secret", "DELETE FROM staging.service_requests")

    def test_aggregate_csv_blocks_spreadsheet_formulas(self):
        result = aggregate_csv([{"label": "=HYPERLINK('x')", "requests": 2},
                                {"label": "+SUM(1,2)", "requests": 4}])
        self.assertIn("'=HYPERLINK", result)
        self.assertIn("'+SUM(1,2)", result)
        self.assertEqual(aggregate_csv([]), "")


if __name__ == "__main__":
    unittest.main()
