-- A missing/extra fact row should break acceptance, not silently skew metrics.
with counts as (
    select
        (select count(*) from {{ ref('stg_service_requests') }}) as staging_rows,
        (select count(*) from {{ ref('fct_service_requests') }}) as fact_rows
)
select * from counts where staging_rows <> fact_rows

