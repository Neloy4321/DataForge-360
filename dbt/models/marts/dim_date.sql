-- Calendar grain: one day observed in the bounded source data.
select distinct
    created_at::date as date_day,
    extract(year from created_at)::integer as year_number,
    extract(quarter from created_at)::integer as quarter_number,
    extract(month from created_at)::integer as month_number,
    trim(to_char(created_at, 'Month')) as month_name,
    extract(isodow from created_at)::integer as iso_day_of_week
from {{ ref('stg_service_requests') }}

