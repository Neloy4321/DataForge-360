-- Phase 2: operational staging warehouse. Source timestamps are timezone-naive.
CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.service_requests (
    unique_key TEXT PRIMARY KEY,
    created_date TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    closed_date TIMESTAMP WITHOUT TIME ZONE,
    agency TEXT,
    agency_name TEXT,
    complaint_type TEXT,
    descriptor TEXT,
    status TEXT,
    resolution_action_updated_date TIMESTAMP WITHOUT TIME ZONE,
    borough TEXT,
    incident_zip TEXT,
    community_board TEXT,
    open_data_channel_type TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    source_payload_hash CHAR(64) NOT NULL,
    source_payload JSONB NOT NULL,
    first_loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT request_latitude_valid CHECK (latitude BETWEEN -90 AND 90),
    CONSTRAINT request_longitude_valid CHECK (longitude BETWEEN -180 AND 180)
);

CREATE INDEX IF NOT EXISTS ix_service_requests_created_date
    ON staging.service_requests (created_date);
CREATE INDEX IF NOT EXISTS ix_service_requests_status
    ON staging.service_requests (status);
CREATE INDEX IF NOT EXISTS ix_service_requests_agency_created
    ON staging.service_requests (agency, created_date);
CREATE INDEX IF NOT EXISTS ix_service_requests_resolution_updated
    ON staging.service_requests (resolution_action_updated_date);
