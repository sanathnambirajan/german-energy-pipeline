select
    ts_local::date as day,
    avg(price_eur_mwh) as avg_price,
    min(price_eur_mwh) as min_price,
    max(price_eur_mwh) as max_price,
    max(price_eur_mwh) - min(price_eur_mwh) as price_spread,
    sum(case when price_eur_mwh < 0 then 1 else 0 end) as negative_price_hours,
    count(*) as hours_with_price
from {{ ref('stg_prices') }}
group by 1
