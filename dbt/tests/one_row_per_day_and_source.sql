select day, source, count(*)
from {{ ref('daily_generation_by_source') }}
group by day, source
having count(*) > 1
