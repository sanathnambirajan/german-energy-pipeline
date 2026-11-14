-- SMARD gives timestamps in ms (UTC). Convert to German local time so that
-- days start at midnight in Germany. Today is left out because it is not complete yet.

select
    filter_id,
    series_name,
    region,
    to_timestamp(ts_ms / 1000.0) at time zone 'Europe/Berlin' as ts_local,
    value
from {{ source('raw', 'smard_hourly') }}
where value is not null
  and to_timestamp(ts_ms / 1000.0) at time zone 'Europe/Berlin' >= '{{ var("start_date", "2020-01-01") }}'
  and to_timestamp(ts_ms / 1000.0) at time zone 'Europe/Berlin'
      < date_trunc('day', now() at time zone 'Europe/Berlin')
