"""NYC 311 Socrata API client with bounded keyset pagination."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Iterator, Mapping
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DATASET_ID = "erm2-nwe9"
DATASET_URL = "https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2020-to-Present/erm2-nwe9"
API_URL = f"https://data.cityofnewyork.us/resource/{DATASET_ID}.json"

# Minimize exposure: omit street-level addresses and free-text descriptions.
FIELDS = (
    "unique_key", "created_date", "closed_date", "agency", "agency_name",
    "complaint_type", "descriptor", "status", "resolution_action_updated_date",
    "borough", "incident_zip", "community_board", "open_data_channel_type",
    "latitude", "longitude",
)
TRANSIENT_HTTP_CODES = {408, 429, 500, 502, 503, 504}
Fetch = Callable[[str, Mapping[str, str]], list[dict[str, Any]]]


def parse_day(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Expected YYYY-MM-DD, got {value!r}") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"Expected YYYY-MM-DD, got {value!r}")
    return parsed


def parse_source_timestamp(value: str) -> datetime:
    """Preserve the source's timezone-naive timestamp; never label it UTC."""
    if not isinstance(value, str):
        raise ValueError("created_date must be a timestamp string")
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid created_date: {value!r}") from exc
    if result.tzinfo is not None:
        raise ValueError("created_date unexpectedly includes a timezone")
    return result


def quote_soql(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def build_url(start: date, end: date, limit: int, cursor: tuple[str, str] | None) -> str:
    if end <= start:
        raise ValueError("End date must be after start date")
    if not 1 <= limit <= 5000:
        raise ValueError("Page size must be between 1 and 5000")
    start_ts = start.isoformat() + "T00:00:00"
    end_ts = end.isoformat() + "T00:00:00"
    where = (f"created_date >= {quote_soql(start_ts)} "
             f"AND created_date < {quote_soql(end_ts)}")
    if cursor:
        created, key = cursor
        where += (f" AND (created_date > {quote_soql(created)} "
                  f"OR (created_date = {quote_soql(created)} "
                  f"AND unique_key > {quote_soql(key)}))")
    query = {
        "$select": ",".join(FIELDS),
        "$where": where,
        "$order": "created_date ASC,unique_key ASC",
        "$limit": str(limit),
    }
    return API_URL + "?" + urlencode(query)


def _retry_after(raw: str | None, fallback: float) -> float:
    if not raw:
        return fallback
    try:
        return max(0.0, min(float(raw), 60.0))
    except ValueError:
        try:
            delta = (parsedate_to_datetime(raw) - datetime.now(timezone.utc)).total_seconds()
            return max(0.0, min(delta, 60.0))
        except (ValueError, TypeError, OverflowError):
            return fallback


def http_fetch_json(
    url: str,
    headers: Mapping[str, str],
    *,
    max_attempts: int = 4,
    sleep: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    """Fetch a JSON array, retrying only transient network/HTTP failures."""
    for attempt in range(max_attempts):
        try:
            with urlopen(Request(url, headers=dict(headers)), timeout=45) as response:
                payload = json.load(response)
            if not isinstance(payload, list) or any(not isinstance(x, dict) for x in payload):
                raise ValueError("NYC 311 API response was not a JSON array of objects")
            return payload
        except HTTPError as exc:
            if exc.code not in TRANSIENT_HTTP_CODES or attempt == max_attempts - 1:
                raise
            delay = _retry_after(exc.headers.get("Retry-After"), 2 ** attempt)
        except (URLError, TimeoutError):
            if attempt == max_attempts - 1:
                raise
            delay = 2 ** attempt
        sleep(delay)
    raise AssertionError("unreachable")


class NYC311Client:
    def __init__(self, fetch: Fetch = http_fetch_json, app_token: str | None = None):
        self.fetch = fetch
        self.app_token = app_token if app_token is not None else os.getenv("NYC311_APP_TOKEN", "")

    def iter_records(
        self, start: date, end: date, *, page_size: int = 1000, max_records: int = 10000
    ) -> Iterator[dict[str, Any]]:
        if max_records < 1:
            raise ValueError("max_records must be at least 1")
        if not 1 <= page_size <= 5000:
            raise ValueError("page_size must be between 1 and 5000")
        headers = {"Accept": "application/json", "User-Agent": "DataForge-360/0.1"}
        if self.app_token:
            headers["X-App-Token"] = self.app_token
        cursor: tuple[str, str] | None = None
        count = 0
        while count < max_records:
            size = min(page_size, max_records - count)
            records = self.fetch(build_url(start, end, size, cursor), headers)
            if len(records) > size:
                raise ValueError("API returned more records than requested")
            if not records:
                return
            for record in records:
                key = record.get("unique_key")
                created = record.get("created_date")
                if not isinstance(key, str) or not key:
                    raise ValueError("Missing unique_key in API response")
                stamp = parse_source_timestamp(created)
                if not (datetime.combine(start, datetime.min.time()) <= stamp
                        < datetime.combine(end, datetime.min.time())):
                    raise ValueError(f"Record {key} is outside requested date range")
                next_cursor = (created, key)
                if cursor is not None and next_cursor <= cursor:
                    raise ValueError("API pagination order did not advance")
                cursor = next_cursor
                yield record
                count += 1
            if len(records) < size:
                return
