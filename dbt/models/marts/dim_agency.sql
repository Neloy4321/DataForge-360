-- One deterministic member per normalized agency code; includes missing-value member.
select
    md5(coalesce(agency_code, '__MISSING__')) as agency_key,
    coalesce(agency_code, 'UNKNOWN') as agency_code,
    coalesce(max(agency_name), 'Unknown agency') as agency_name,
    count(*) as staging_request_count
from {{ ref('stg_service_requests') }}
group by agency_code

