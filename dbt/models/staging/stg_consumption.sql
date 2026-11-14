select
    ts_local,
    value as consumption_mwh
from {{ ref('stg_smard_hourly') }}
where series_name = 'consumption'
