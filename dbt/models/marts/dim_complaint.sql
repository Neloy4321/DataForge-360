select
    md5(coalesce(complaint_type, '__MISSING__')) as complaint_key,
    coalesce(complaint_type, 'UNKNOWN') as complaint_type,
    count(*) as staging_request_count
from {{ ref('stg_service_requests') }}
group by complaint_type

