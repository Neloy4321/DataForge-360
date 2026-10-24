"""Command line entry point for reproducible, bounded ingestion."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .pipeline import ingest_window
from .source import NYC311Client, parse_day


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download bounded NYC 311 records")
    parser.add_argument("--start", required=True, help="YYYY-MM-DD, inclusive")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD, exclusive")
    parser.add_argument("--max-records", type=int, default=10000)
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw"))
    args = parser.parse_args(argv)
    try:
        summary = ingest_window(
            NYC311Client(), parse_day(args.start), parse_day(args.end),
            output_dir=args.output_dir,
            page_size=args.page_size,
            max_records=args.max_records,
        )
    except (ValueError, OSError, TimeoutError, RuntimeError) as exc:
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2))
    return 0
