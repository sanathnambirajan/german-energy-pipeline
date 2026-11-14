-- one row per day with share and price together, used for the price vs renewables chart

select
    r.day,
    extract(year from r.day)::int as year,
    extract(month from r.day)::int as month,
    r.renewable_share,
    r.renewable_share_of_consumption,
    r.wind_mwh,
    r.solar_mwh,
    r.total_generation_mwh,
    r.consumption_mwh,
    p.avg_price,
    p.min_price,
    p.max_price,
    p.negative_price_hours
from {{ ref('daily_renewable_share') }} r
left join {{ ref('daily_price_stats') }} p on r.day = p.day
