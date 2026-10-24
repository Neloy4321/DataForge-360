-- One row per known NYC 311 request. Do not assume source-local timestamps are UTC.
select
    unique_key as service_request_id,
    created_date as created_at,
    closed_date as closed_at,
    nullif(upper(btrim(agency)), '') as agency_code,
    nullif(btrim(agency_name), '') as agency_name,
    nullif(btrim(complaint_type), '') as complaint_type,
    nullif(btrim(descriptor), '') as descriptor,
    nullif(btrim(status), '') as request_status,
    nullif(upper(btrim(borough)), '') as borough,
    nullif(btrim(incident_zip), '') as incident_zip,
    nullif(btrim(community_board), '') as community_board,
    nullif(btrim(open_data_channel_type), '') as open_data_channel_type,
    resolution_action_updated_date as resolution_action_updated_at,
    latitude,
    longitude,
    source_payload_hash,
    last_changed_at as staging_last_changed_at
from {{ source('nyc311', 'service_requests') }}

