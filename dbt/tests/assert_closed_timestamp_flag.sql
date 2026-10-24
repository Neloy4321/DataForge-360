select service_request_id
from {{ ref('fct_service_requests') }}
where has_closed_timestamp is distinct from (closed_at is not null)

