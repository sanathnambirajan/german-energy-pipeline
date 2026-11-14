with generation as (
    select
        day,
        sum(case when category = 'renewable' then generation_mwh else 0 end) as renewable_mwh,
        sum(case when category = 'conventional' then generation_mwh else 0 end) as conventional_mwh,
        sum(case when source in ('wind_onshore', 'wind_offshore') then generation_mwh else 0 end) as wind_mwh,
        sum(case when source = 'solar' then generation_mwh else 0 end) as solar_mwh,
        sum(generation_mwh) as total_generation_mwh
    from {{ ref('daily_generation_by_source') }}
    group by day
),

consumption as (
    select
        ts_local::date as day,
        sum(consumption_mwh) as consumption_mwh
    from {{ ref('stg_consumption') }}
    group by 1
)

select
    g.day,
    g.renewable_mwh,
    g.conventional_mwh,
    g.wind_mwh,
    g.solar_mwh,
    g.total_generation_mwh,
    c.consumption_mwh,
    g.renewable_mwh / nullif(g.total_generation_mwh, 0) as renewable_share,
    g.renewable_mwh / nullif(c.consumption_mwh, 0) as renewable_share_of_consumption
from generation g
left join consumption c on g.day = c.day
