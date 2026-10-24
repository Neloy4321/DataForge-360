# PostgreSQL staging warehouse (Phase 2)

## What is implemented

- PostgreSQL 16 staging schema (`warehouse/schema.sql`) with primary key on
  `unique_key`, source-local timestamps, nullable optional dimensions, and
  focused indexes for date, status, agency and update-date queries.
- A local Docker Compose service bound only to `127.0.0.1:55432` with a password
  provided outside version control. Resource settings are deliberately modest
  for an 8 GB Windows laptop.
- Bounded Python loader (`python -m dataforge.warehouse`), with an explicit
  Psycopg dependency isolated from the Phase 1 standard-library installation.
- Mandatory preflight SHA-256 and row-count verification against the ingestion
  manifest, plus per-record type/range validation before database writes.
- Transactional batches of at most 5,000 rows (500 by default).
- PostgreSQL `ON CONFLICT (unique_key) DO UPDATE` with a payload-hash predicate:
  unchanged source records are not rewritten, while changed records update.
- Deterministic unit tests and a separate real-PostgreSQL CI integration test.

## Operational guarantees and limitations

The schema stores one row per `unique_key`. Replaying an identical snapshot
should produce `rows_inserted_or_updated = 0` after its first successful load.
Changed source values can update existing rows, including status and closed
date. `first_loaded_at` remains stable while `last_changed_at` advances on a
change. ZIP and unique-key identifiers remain text, preserving leading zeros.

Each batch commits independently. A failure after an earlier committed batch
can leave a partially loaded snapshot, but a complete rerun safely converges
to the final state. This is **not** a distributed all-or-nothing transaction.

**Still outstanding:** Scheduling, source-side change detection/watermarks,
late-arriving record reconciliation across all historical dates, enterprise
quality thresholds, analytic star schema, dbt marts, and hosted monitoring.
Specifically, `created_date` alone is not sufficient for change-data capture.
These requirements remain separate acceptance items.

## Acceptance checks

The integration test uses an isolated PostgreSQL service and a unique test key:

1. Insert a verified raw snapshot once: one new database row.
2. Load the same snapshot: zero changed rows.
3. Change the source status and closed date; regenerate its verified snapshot.
4. Reload: exactly one matching database row, with updated status.
5. Confirm the ZIP identifier is preserved as text and remove only the test row.

GitHub Actions runs the database test against a dedicated CI Postgres container;
the local test suite skips it if `DATAFORGE_TEST_DATABASE_URL` is absent.
