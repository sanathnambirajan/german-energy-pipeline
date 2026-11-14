select *
from {{ ref('daily_renewable_share') }}
where renewable_share < 0 or renewable_share > 1
