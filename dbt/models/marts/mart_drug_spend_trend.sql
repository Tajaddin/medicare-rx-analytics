-- Florida Part D spend per generic name, class and year, with year-over-year growth and the national cost per
-- claim. Class is part of the grain because one generic name can serve two uses (buprenorphine: pain patches
-- and OUD treatment). Growth compares with the calendar year before; after a year without Florida claims it is
-- empty, not growth over two years.
with fl as (
    select
        generic_name,
        drug_class,
        data_year,
        sum(total_claims) as claims,
        sum(total_30day_fills) as fills_30day,
        sum(total_drug_cost) as drug_cost,
        count(distinct npi) as prescribers
    from {{ ref('int_prescriber_drug') }}
    group by generic_name, drug_class, data_year
),

national as (
    select generic_name, data_year, sum(total_spending) / nullif(sum(total_claims), 0) as national_cost_per_claim
    from {{ ref('stg_spending_by_drug') }}
    group by generic_name, data_year
)

select
    fl.generic_name,
    fl.drug_class,
    fl.data_year,
    fl.claims,
    fl.fills_30day,
    fl.drug_cost,
    fl.prescribers,
    fl.drug_cost / nullif(fl.claims, 0) as cost_per_claim,
    n.national_cost_per_claim,
    fl.drug_cost / nullif(prev.drug_cost, 0) - 1 as cost_growth_yoy,
    rank() over (partition by fl.data_year order by fl.drug_cost desc) as cost_rank_in_year
from fl
left join fl as prev
    on fl.generic_name = prev.generic_name and fl.drug_class = prev.drug_class and fl.data_year = prev.data_year + 1
left join national as n
    on upper(fl.generic_name) = upper(n.generic_name) and fl.data_year = n.data_year
