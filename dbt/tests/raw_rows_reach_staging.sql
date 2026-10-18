-- Every raw record of every year becomes exactly one staging row (nothing dropped by a failed cast).
select r.data_year, r.n as raw_rows, s.n as staging_rows
from (
    select data_year, count(*) as n from {{ source('raw', 'partd_prescriber_drug') }} group by data_year
) as r
left join (
    select data_year, count(*) as n from {{ ref('stg_prescriber_drug') }} group by data_year
) as s using (data_year)
where s.n is null or s.n <> r.n
