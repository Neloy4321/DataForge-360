-- Bad source clocks may exist, but derived duration cannot be negative or fabricated.
select service_request_id
from {{ ref('fct_service_requests') }}
where resolution_hours < 0
   or (closed_at is null and resolution_hours is not null)
   or (closed_at < created_at and resolution_hours is not null)

