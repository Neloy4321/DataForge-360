"""Atomic, bounded raw ingestion of NYC 311 records."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

from .source import DATASET_ID, DATASET_URL, NYC311Client


def ingest_window(
    client: NYC311Client,
    start: date,
    end: date,
    *,
    output_dir: Path,
    page_size: int = 1000,
    max_records: int = 10000,
) -> dict:
    """Replace one deterministic window atomically; preserve no partial output.

    Raw JSONL and metadata are kept outside git. A repeated window invocation
    overwrites its own snapshot rather than appending duplicate records.
    """
    if end <= start:
        raise ValueError("End date must be after start date")
    if max_records < 1:
        raise ValueError("max_records must be at least 1")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"nyc311_{start.isoformat()}_{end.isoformat()}"
    result_path = output_dir / f"{stem}.jsonl.gz"
    manifest_path = output_dir / f"{stem}.manifest.json"
    staged_path = output_dir / f"{stem}.jsonl.gz.partial"
    staged_manifest = output_dir / f"{stem}.manifest.json.partial"
    count = 0
    digest = hashlib.sha256()
    try:
        with gzip.open(staged_path, "wb", compresslevel=6) as output:
            for record in client.iter_records(
                start, end, page_size=page_size, max_records=max_records
            ):
                line = (json.dumps(record, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":")) + "\n").encode("utf-8")
                output.write(line)
                digest.update(line)
                count += 1
        manifest = {
            "dataset_id": DATASET_ID,
            "source_url": DATASET_URL,
            "window_start_inclusive": start.isoformat(),
            "window_end_exclusive": end.isoformat(),
            "rows_written": count,
            "max_records": max_records,
            # Reaching the cap does not prove more source records exist.
            "reached_max_records": count == max_records,
            "page_size": page_size,
            "content_sha256_uncompressed": digest.hexdigest(),
            "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
            "file": result_path.name,
            "created_date_timezone": "source-local/unspecified (not converted to UTC)",
        }
        staged_manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        os.replace(staged_path, result_path)
        os.replace(staged_manifest, manifest_path)
        return manifest
    finally:
        staged_path.unlink(missing_ok=True)
        staged_manifest.unlink(missing_ok=True)
