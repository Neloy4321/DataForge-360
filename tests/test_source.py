import io
import json
import unittest
from datetime import date
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from dataforge.source import (
    NYC311Client, build_url, http_fetch_json, parse_day,
    parse_source_timestamp, quote_soql,
)


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.start = date(2026, 9, 1)
        self.end = date(2026, 9, 8)

    def test_query_uses_half_open_date_window_and_sorted_keyset(self):
        url = build_url(self.start, self.end, 50, ("2026-09-01T10:00:00.000", "123"))
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(query["$limit"], ["50"])
        self.assertEqual(query["$order"], ["created_date ASC,unique_key ASC"])
        self.assertIn("created_date < '2026-09-08T00:00:00'", query["$where"][0])
        self.assertIn("unique_key > '123'", query["$where"][0])
        self.assertNotIn("incident_address", query["$select"][0])

    def test_quote_soql_escapes_quotes(self):
        self.assertEqual(quote_soql("a'b"), "'a''b'")

    def test_rejects_bad_date_and_page_size(self):
        with self.assertRaises(ValueError):
            parse_day("2026-9-1")
        with self.assertRaises(ValueError):
            build_url(self.start, self.end, 5001, None)
        with self.assertRaises(ValueError):
            build_url(self.end, self.start, 5, None)

    def test_source_timestamps_are_naive(self):
        self.assertIsNone(parse_source_timestamp("2026-09-01T10:00:00.000").tzinfo)
        with self.assertRaises(ValueError):
            parse_source_timestamp("2026-09-01T10:00:00+00:00")

    def test_keyset_pagination_and_cap(self):
        pages = [
            [{"unique_key": "1", "created_date": "2026-09-01T10:00:00"},
             {"unique_key": "2", "created_date": "2026-09-01T10:00:00"}],
            [{"unique_key": "3", "created_date": "2026-09-02T10:00:00"}],
        ]
        calls = []

        def fetch(url, headers):
            calls.append((parse_qs(urlsplit(url).query), headers))
            return pages.pop(0)

        records = list(NYC311Client(fetch=fetch, app_token="test-token").iter_records(
            self.start, self.end, page_size=2, max_records=3))
        self.assertEqual([r["unique_key"] for r in records], ["1", "2", "3"])
        self.assertEqual(calls[-1][0]["$limit"], ["1"])
        self.assertIn("unique_key > '2'", calls[-1][0]["$where"][0])
        self.assertEqual(calls[0][1]["X-App-Token"], "test-token")

    def test_rejects_unsorted_or_duplicate_data(self):
        def fetch(url, headers):
            return [{"unique_key": "2", "created_date": "2026-09-01T10:00:00"},
                    {"unique_key": "1", "created_date": "2026-09-01T10:00:00"}]
        with self.assertRaisesRegex(ValueError, "order did not advance"):
            list(NYC311Client(fetch=fetch).iter_records(self.start, self.end, page_size=2))

    def test_rejects_out_of_window(self):
        def fetch(url, headers):
            return [{"unique_key": "1", "created_date": "2026-08-31T23:59:59"}]
        with self.assertRaisesRegex(ValueError, "outside requested"):
            list(NYC311Client(fetch=fetch).iter_records(self.start, self.end))

    def test_retries_503_and_respects_retry_after(self):
        class Response:
            def __enter__(self):
                return io.BytesIO(json.dumps([{"unique_key": "1"}]).encode())
            def __exit__(self, *args):
                return False
        error = HTTPError("https://example.com", 503, "busy", {"Retry-After": "2"}, None)
        sleeps = []
        with patch("dataforge.source.urlopen", side_effect=[error, Response()]):
            result = http_fetch_json("https://example.com", {}, sleep=sleeps.append)
        self.assertEqual(result, [{"unique_key": "1"}])
        self.assertEqual(sleeps, [2.0])

    def test_rejects_unexpected_response_shape(self):
        class Response:
            def __enter__(self):
                return io.BytesIO(b'{"error":"unauthorized"}')
            def __exit__(self, *args):
                return False
        with patch("dataforge.source.urlopen", return_value=Response()):
            with self.assertRaisesRegex(ValueError, "not a JSON array"):
                http_fetch_json("https://example.com", {})


if __name__ == "__main__":
    unittest.main()
