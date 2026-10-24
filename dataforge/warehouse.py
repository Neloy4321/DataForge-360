"""Verified gzip JSONL -> PostgreSQL operational staging warehouse.

Dependencies are imported lazily so Phase 1's offline tests stay stdlib-only.
Each small batch commits independently and can safely be replayed.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import sys
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_SQL = Path(__file__).resolve().parent.parent / "warehouse" / "schema.sql"

UPSERT_SQL = """
INSERT INTO staging.service_requests (
    unique_key, created_date, closed_date, agency, agency_name, complaint_type,
    descriptor, status, resolution_action_updated_date, borough, incident_zip,
    community_board, open_data_channel_type, latitude, longitude,
    source_payload_hash, source_payload
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb
)
ON CONFLICT (unique_key) DO UPDATE SET
    created_date = EXCLUDED.created_date,
    closed_date = EXCLUDED.closed_date,
    agency = EXCLUDED.agency,
    agency_name = EXCLUDED.agency_name,
    complaint_type = EXCLUDED.complaint_type,
    descriptor = EXCLUDED.descriptor,
    status = EXCLUDED.status,
    resolution_action_updated_date = EXCLUDED.resolution_action_updated_date,
    borough = EXCLUDED.borough,
    incident_zip = EXCLUDED.incident_zip,
    community_board = EXCLUDED.community_board,
    open_data_channel_type = EXCLUDED.open_data_channel_type,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude,
    source_payload_hash = EXCLUDED.source_payload_hash,
    source_payload = EXCLUDED.source_payload,
    last_changed_at = CURRENT_TIMESTAMP
WHERE staging.service_requests.source_payload_hash
    IS DISTINCT FROM EXCLUDED.source_payload_hash
"""


def _optional_timestamp(value: Any, field: str) -> datetime | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a timestamp string")
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid {field}: {value!r}") from exc
    if dt.tzinfo is not None:
        raise ValueError(f"{field} must not invent a timezone")
    return dt


def _optional_coordinate(value: Any, field: str, lower: float, upper: float) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {field}: {value!r}") from exc
    if not math.isfinite(number) or not lower <= number <= upper:
        raise ValueError(f"{field} outside valid range: {value!r}")
    return number


def normalize_record(rec: dict[str, Any]) -> tuple[Any, ...]:
    """Use source identifiers as text, preserving ZIP leading zeros and nulls."""
    if not isinstance(rec, dict):
        raise ValueError("Source record must be an object")
    key = rec.get("unique_key")
    if not isinstance(key, str) or not key:
        raise ValueError("Missing unique_key")
    created = _optional_timestamp(rec.get("created_date"), "created_date")
    if created is None:
        raise ValueError("Missing created_date")
    payload = json.dumps(rec, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return (
        key, created, _optional_timestamp(rec.get("closed_date"), "closed_date"),
        rec.get("agency"), rec.get("agency_name"), rec.get("complaint_type"),
        rec.get("descriptor"), rec.get("status"),
        _optional_timestamp(rec.get("resolution_action_updated_date"),
                            "resolution_action_updated_date"),
        rec.get("borough"), rec.get("incident_zip"), rec.get("community_board"),
        rec.get("open_data_channel_type"),
        _optional_coordinate(rec.get("latitude"), "latitude", -90, 90),
        _optional_coordinate(rec.get("longitude"), "longitude", -180, 180),
        payload_hash, payload,
    )


def _iter_lines(snapshot: Path) -> Iterator[bytes]:
    with gzip.open(snapshot, "rb") as stream:
        for line in stream:
            if not line.strip():
                raise ValueError("Blank record in raw snapshot")
            yield line


def verify_snapshot(snapshot: Path) -> dict[str, Any]:
    """Reject missing or altered raw snapshots before any database mutation."""
    snapshot = Path(snapshot)
    if not snapshot.name.endswith(".jsonl.gz"):
        raise ValueError("Expected a .jsonl.gz snapshot")
    manifest_path = snapshot.with_name(
        snapshot.name.removesuffix(".jsonl.gz") + ".manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("dataset_id") != "erm2-nwe9" or manifest.get("file") != snapshot.name:
        raise ValueError("Snapshot provenance/filename mismatch")
    sha = hashlib.sha256()
    count = 0
    for line_no, line in enumerate(_iter_lines(snapshot), start=1):
        sha.update(line)
        count += 1
        try:
            normalize_record(json.loads(line))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid snapshot record on line {line_no}: {exc}") from exc
    if count != manifest.get("rows_written"):
        raise ValueError("Raw snapshot row-count mismatch")
    if sha.hexdigest() != manifest.get("content_sha256_uncompressed"):
        raise ValueError("Raw snapshot SHA-256 mismatch")
    return manifest


def _iter_normalized(snapshot: Path) -> Iterator[tuple[Any, ...]]:
    for line_no, raw_line in enumerate(_iter_lines(snapshot), start=1):
        try:
            yield normalize_record(json.loads(raw_line))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid snapshot record on line {line_no}: {exc}") from exc


def load_snapshot(snapshot: Path, dsn: str, *, batch_size: int = 500) -> dict[str, Any]:
    if batch_size < 1 or batch_size > 5000:
        raise ValueError("batch_size must be in 1..5000")
    if not dsn:
        raise ValueError("DATABASE_URL is required")
    snapshot = Path(snapshot)
    manifest = verify_snapshot(snapshot)
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError('Install warehouse dependencies: pip install "psycopg[binary]"') from exc

    processed = 0
    changed = 0
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
        conn.commit()
        stream = iter(_iter_normalized(snapshot))
        while True:
            batch = []
            for _ in range(batch_size):
                try:
                    batch.append(next(stream))
                except StopIteration:
                    break
            if not batch:
                break
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.executemany(UPSERT_SQL, batch)
                    modified_this_batch = cur.rowcount
            processed += len(batch)
            changed += modified_this_batch
    return {
        "snapshot": snapshot.name,
        "manifest_sha256": manifest["content_sha256_uncompressed"],
        "rows_read": processed,
        "rows_inserted_or_updated": changed,
        "rows_unchanged": processed - changed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load a verified raw NYC 311 snapshot into PostgreSQL")
    parser.add_argument("--input", required=True, type=Path, help="Path to .jsonl.gz snapshot")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args(argv)
    try:
        report = load_snapshot(args.input, os.getenv("DATABASE_URL", ""),
                               batch_size=args.batch_size)
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"Warehouse load failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
