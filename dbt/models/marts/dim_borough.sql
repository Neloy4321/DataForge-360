select
    md5(coalesce(borough, '__MISSING__')) as borough_key,
    coalesce(borough, 'UNKNOWN') as borough_name,
    count(*) as staging_request_count
from {{ ref('stg_service_requests') }}
group by borough

