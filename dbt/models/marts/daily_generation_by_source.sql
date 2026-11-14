select
    ts_local::date as day,
    source,
    source_label,
    category,
    sum(generation_mwh) as generation_mwh
from {{ ref('stg_generation') }}
group by 1, 2, 3, 4
