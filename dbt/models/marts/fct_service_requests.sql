-- Fact grain: latest known state of one service request, NOT request-event history.
select
    service_request_id,
    md5(coalesce(agency_code, '__MISSING__')) as agency_key,
    md5(coalesce(borough, '__MISSING__')) as borough_key,
    md5(coalesce(complaint_type, '__MISSING__')) as complaint_key,
    created_at::date as created_day,
    created_at,
    closed_at,
    request_status,
    descriptor,
    incident_zip,
    community_board,
    open_data_channel_type,
    resolution_action_updated_at,
    latitude,
    longitude,
    (closed_at is not null) as has_closed_timestamp,
    case
        when closed_at >= created_at
            then round(extract(epoch from (closed_at - created_at)) / 3600.0, 2)
        else null
    end as resolution_hours,
    source_payload_hash,
    staging_last_changed_at
from {{ ref('stg_service_requests') }}

