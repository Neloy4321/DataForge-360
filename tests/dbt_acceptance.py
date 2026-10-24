"""Deterministic end-to-end dbt fixture, ONLY against an isolated CI database.

Usage: python tests/dbt_acceptance.py seed|verify
No NYC API, application credentials or production data are needed.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CI_KEYS = ("df_dbt_ci_open", "df_dbt_ci_closed", "df_dbt_ci_unknown", "df_dbt_ci_bad_clock")
FIXTURES = [
    {
        "unique_key": CI_KEYS[0], "created_date": "2026-09-01T10:00:00",
        "agency": " dot ", "agency_name": "Department of Transportation",
        "borough": " brooklyn ", "complaint_type": " Pothole ",
        "status": "Open", "incident_zip": "00102",
    },
    {
        "unique_key": CI_KEYS[1], "created_date": "2026-09-01T12:00:00",
        "closed_date": "2026-09-01T14:00:00", "agency": "DOT",
        "agency_name": "Department of Transportation", "borough": "BROOKLYN",
        "complaint_type": "Pothole", "status": "Closed", "incident_zip": "00102",
    },
    {
        "unique_key": CI_KEYS[2], "created_date": "2026-09-02T09:00:00",
        "status": "Open", "incident_zip": None,
    },
    {
        "unique_key": CI_KEYS[3], "created_date": "2026-09-02T16:00:00",
        "closed_date": "2026-09-02T15:00:00", "agency": "DEP",
        "borough": "Queens", "complaint_type": "Water Leak", "status": "Closed",
    },
]


def require_ci_db(conn) -> None:
    if conn.info.dbname != "dataforge_ci":
        raise RuntimeError("Refusing to seed or verify anything outside dataforge_ci")


def seed(conn) -> None:
    with conn.cursor() as cur:
        cur.execute((ROOT / "warehouse" / "schema.sql").read_text(encoding="utf-8"))
        for record in FIXTURES:
            payload = json.dumps(record, sort_keys=True, separators=(",", ":"))
            digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            cur.execute(
                """insert into staging.service_requests
                   (unique_key, created_date, closed_date, agency, agency_name,
                    borough, complaint_type, status, incident_zip,
                    source_payload_hash, source_payload)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                   on conflict (unique_key) do nothing""",
                (record["unique_key"], datetime.fromisoformat(record["created_date"]),
                 datetime.fromisoformat(record["closed_date"])
                 if record.get("closed_date") else None, record.get("agency"),
                 record.get("agency_name"), record.get("borough"),
                 record.get("complaint_type"), record.get("status"),
                 record.get("incident_zip"), digest, payload),
            )
    print("Seeded 4 synthetic rows into isolated dataforge_ci")


def verify(conn) -> None:
    schema_name = os.getenv("DBT_SCHEMA", "analytics_ci") + "_marts"
    import psycopg

    from psycopg import sql
    with conn.cursor() as cur:
        fact = sql.Identifier(schema_name, "fct_service_requests")
        cur.execute(sql.SQL("select service_request_id, incident_zip, resolution_hours, "
                            "has_closed_timestamp from {} order by service_request_id").format(fact))
        found = {key: (zipcode, duration, has_closed)
                 for key, zipcode, duration, has_closed in cur.fetchall()}
        assert set(found) == set(CI_KEYS), f"Missing or extra fixture records: {found!r}"
        assert found[CI_KEYS[0]] == ("00102", None, False), found[CI_KEYS[0]]
        assert float(found[CI_KEYS[1]][1]) == 2.0, found[CI_KEYS[1]]
        assert found[CI_KEYS[1]][2] is True, found[CI_KEYS[1]]
        assert found[CI_KEYS[3]][1] is None, "Negative duration should be NULL"

        for dimension, expected_count in (
            ("dim_agency", 3), ("dim_borough", 3), ("dim_complaint", 3),
            ("dim_date", 2),
        ):
            cur.execute(sql.SQL("select count(*) from {}").format(
                sql.Identifier(schema_name, dimension)))
            actual = cur.fetchone()[0]
            assert actual == expected_count, (dimension, actual, expected_count)

        cur.execute(sql.SQL("select agency_code from {} where agency_code = 'DOT'").format(
            sql.Identifier(schema_name, "dim_agency")))
        assert cur.fetchall() == [("DOT",)], "Agency normalization/merging failed"
        cur.execute(sql.SQL("select borough_name from {} where borough_name = 'UNKNOWN'").format(
            sql.Identifier(schema_name, "dim_borough")))
        assert cur.fetchall() == [("UNKNOWN",)], "Unknown borough member absent"
    print("PASS: fact grain, ZIP preservation, 2-hour duration, bad-clock handling, "
          "dimension cardinality and unknown-member handling")


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"seed", "verify"}:
        raise SystemExit("Usage: python tests/dbt_acceptance.py seed|verify")
    dsn = os.getenv("DATAFORGE_TEST_DATABASE_URL")
    if not dsn:
        raise SystemExit("Dedicated DATAFORGE_TEST_DATABASE_URL is required")
    import psycopg

    with psycopg.connect(dsn) as conn:
        require_ci_db(conn)
        if sys.argv[1] == "seed":
            seed(conn)
        else:
            verify(conn)


if __name__ == "__main__":
    main()

