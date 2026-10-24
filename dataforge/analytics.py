"""Read-only, bounded PostgreSQL analytics for the NYC 311 dashboard.

All metrics are calculated from the dbt request-grain fact and dimensions.
No record-level exports, raw addresses, or free-text fields are exposed.
"""

from __future__ import annotations

import re
import csv
import io
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

MAX_FILTER_VALUES = 30
MAX_WINDOW_DAYS = 366
MAP_MIN_GROUP = 5
MAP_LIMIT = 400


@dataclass(frozen=True)
class DashboardFilters:
    start: date
    end: date  # Inclusive source-local calendar date.
    boroughs: tuple[str, ...] = ()
    agencies: tuple[str, ...] = ()
    complaints: tuple[str, ...] = ()
    statuses: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.start, date) or not isinstance(self.end, date):
            raise ValueError("Select two valid dates")
        days = (self.end - self.start).days
        if days < 0 or days > MAX_WINDOW_DAYS:
            raise ValueError(f"Date window must span 1 to {MAX_WINDOW_DAYS + 1} calendar days")
        for values in (self.boroughs, self.agencies, self.complaints, self.statuses):
            if (not isinstance(values, tuple) or len(values) > MAX_FILTER_VALUES
                    or any(not isinstance(v, str) or not v.strip() or len(v) > 200
                           for v in values)):
                raise ValueError("Invalid category selection")


def marts_schema(prefix: str = "analytics") -> str:
    """Quote only a strictly validated single PostgreSQL schema identifier."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,56}", prefix):
        raise ValueError("DBT_SCHEMA must be a simple identifier of at most 57 chars")
    return f'"{prefix}_marts"'


def _from_marts(prefix: str) -> str:
    schema = marts_schema(prefix)
    return (
        f'FROM {schema}."fct_service_requests" AS f '
        f'JOIN {schema}."dim_agency" AS a ON f.agency_key = a.agency_key '
        f'JOIN {schema}."dim_borough" AS b ON f.borough_key = b.borough_key '
        f'JOIN {schema}."dim_complaint" AS c ON f.complaint_key = c.complaint_key'
    )


def selected_cte(filters: DashboardFilters, prefix: str) -> tuple[str, tuple[Any, ...]]:
    """Build safe SQL with bound filter values; only reviewed columns are selected."""
    clauses = ["f.created_day BETWEEN %s AND %s"]
    parameters: list[Any] = [filters.start, filters.end]
    for attribute, column in (
        ("boroughs", "b.borough_name"),
        ("agencies", "a.agency_code"),
        ("complaints", "c.complaint_type"),
        ("statuses", "f.request_status"),
    ):
        values = getattr(filters, attribute)
        if values:
            clauses.append(f"{column} = ANY(%s)")
            parameters.append(list(values))
    cte = (
        "WITH selected AS (SELECT f.created_day, f.request_status, "
        "f.resolution_hours, f.latitude, f.longitude, "
        "a.agency_code, b.borough_name, c.complaint_type "
        + _from_marts(prefix) + " WHERE " + " AND ".join(clauses) + ") "
    )
    return cte, tuple(parameters)


Metric = Literal["overview", "daily", "borough", "agency", "complaint", "status", "map"]


def metric_query(metric: Metric, filters: DashboardFilters, *, prefix: str = "analytics"
                 ) -> tuple[str, tuple[Any, ...]]:
    cte, parameters = selected_cte(filters, prefix)
    closed = "lower(coalesce(request_status, '')) = 'closed'"
    if metric == "overview":
        statement = (
            "SELECT count(*) AS total_requests, "
            f"count(*) FILTER (WHERE {closed}) AS closed_requests, "
            "count(resolution_hours) AS valid_resolution_count, "
            "round(avg(resolution_hours)::numeric, 1) AS avg_resolution_hours, "
            "round((percentile_cont(0.5) WITHIN GROUP "
            "(ORDER BY resolution_hours))::numeric, 1) AS median_resolution_hours "
            "FROM selected"
        )
    elif metric == "daily":
        statement = (
            "SELECT created_day AS day, count(*) AS requests, "
            f"count(*) FILTER (WHERE {closed}) AS closed_requests "
            "FROM selected GROUP BY 1 ORDER BY 1"
        )
    elif metric in {"borough", "agency", "complaint", "status"}:
        column = {"borough": "borough_name", "agency": "agency_code",
                  "complaint": "complaint_type", "status": "request_status"}[metric]
        statement = (
            f"SELECT coalesce(nullif({column}, ''), 'UNKNOWN') AS label, "
            "count(*) AS requests, "
            f"count(*) FILTER (WHERE {closed}) AS closed_requests, "
            "round((percentile_cont(0.5) WITHIN GROUP "
            "(ORDER BY resolution_hours))::numeric, 1) AS median_resolution_hours "
            "FROM selected GROUP BY 1 ORDER BY requests DESC, label ASC LIMIT 15"
        )
    elif metric == "map":
        statement = (
            "SELECT round(latitude::numeric, 2)::double precision AS lat, "
            "round(longitude::numeric, 2)::double precision AS lon, "
            "count(*) AS requests FROM selected "
            "WHERE latitude BETWEEN 40 AND 41.5 "
            "AND longitude BETWEEN -75 AND -73 "
            f"GROUP BY 1, 2 HAVING count(*) >= {MAP_MIN_GROUP} "
            f"ORDER BY requests DESC LIMIT {MAP_LIMIT}"
        )
    else:
        raise ValueError("Unsupported dashboard metric")
    return cte + statement, parameters


def extent_query(*, prefix: str = "analytics") -> tuple[str, tuple]:
    schema = marts_schema(prefix)
    return (f'SELECT min(created_day) AS first_day, max(created_day) AS last_day, '
            f'count(*) AS fact_rows FROM {schema}."fct_service_requests"', ())


def dimension_options_query(dimension: Literal["borough", "agency", "complaint", "status"],
                            *, prefix: str = "analytics") -> tuple[str, tuple]:
    schema = marts_schema(prefix)
    if dimension == "status":
        return (f'SELECT DISTINCT request_status AS label FROM '
                f'{schema}."fct_service_requests" WHERE request_status IS NOT NULL '
                f'ORDER BY 1 LIMIT 500', ())
    table, column = {"borough": ("dim_borough", "borough_name"),
                     "agency": ("dim_agency", "agency_code"),
                     "complaint": ("dim_complaint", "complaint_type")}[dimension]
    return (f'SELECT "{column}" AS label FROM {schema}."{table}" '
            f'ORDER BY 1 LIMIT 500', ())


def fetch_rows(dsn: str, statement: str, parameters: tuple = ()) -> list[dict]:
    """Use short-lived, read-only transactions; never print a secret-bearing DSN."""
    if not isinstance(dsn, str) or not dsn:
        raise ValueError("DATABASE_URL is required")
    if not statement.lstrip().upper().startswith(("SELECT ", "WITH ")):
        raise ValueError("Only analytics SELECT queries are allowed")
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(
        dsn, connect_timeout=5,
        options="-c default_transaction_read_only=on -c statement_timeout=20000",
        row_factory=dict_row,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(statement, parameters)
            return [dict(row) for row in cursor.fetchall()]


def aggregate_csv(rows: list[dict]) -> str:
    """Export aggregate-only data, neutralizing Excel/Sheets formula cells."""
    if not rows:
        return ""
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]), extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        escaped = {}
        for key in rows[0]:
            value = row.get(key)
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                value = "'" + value
            escaped[key] = value
        writer.writerow(escaped)
    return output.getvalue()
