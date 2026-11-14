select
    s.ts_local,
    s.series_name as source,
    e.source_label,
    e.category,
    s.value as generation_mwh
from {{ ref('stg_smard_hourly') }} s
join {{ ref('energy_sources') }} e
    on s.series_name = e.series_name
