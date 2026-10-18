-- One row per brand x generic product seen in Florida, with its class and national 2024 unit price.
with fl as (
    select
        brand_name,
        generic_name,
        any_value(drug_class) as drug_class,
        any_value(is_brand) as is_brand,
        sum(total_claims) as fl_claims_all_years,
        sum(total_drug_cost) as fl_cost_all_years
    from {{ ref('int_prescriber_drug') }}
    group by brand_name, generic_name
),

national_2024 as (
    select brand_name, generic_name, manufacturers, avg_spend_per_unit, avg_spend_per_claim, price_outlier
    from {{ ref('stg_spending_by_drug') }}
    where data_year = 2024
    qualify row_number() over (partition by brand_name, generic_name order by total_spending desc) = 1
)

select
    fl.brand_name,
    fl.generic_name,
    fl.drug_class,
    fl.is_brand,
    fl.fl_claims_all_years,
    fl.fl_cost_all_years,
    n.manufacturers as national_manufacturers_2024,
    n.avg_spend_per_unit as national_spend_per_unit_2024,
    n.avg_spend_per_claim as national_spend_per_claim_2024,
    coalesce(n.price_outlier, false) as national_price_outlier_2024
from fl
left join national_2024 as n
    on upper(fl.brand_name) = upper(n.brand_name) and upper(fl.generic_name) = upper(n.generic_name)
