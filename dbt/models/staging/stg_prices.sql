-- day-ahead price for the bidding zone Germany/Luxembourg, in EUR per MWh

select
    ts_local,
    value as price_eur_mwh
from {{ ref('stg_smard_hourly') }}
where series_name = 'day_ahead_price'
