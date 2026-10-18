-- Brand-name spend where a generic with the same generic name was also dispensed in Florida that year, and an
-- upper-bound estimate of the saving if every brand 30-day fill had cost what the generic's did.
-- Upper bound: the generic name groups strengths and forms, and some brands have no interchangeable generic.
with by_type as (
    select
        generic_name,
        any_value(drug_class) as drug_class,
        data_year,
        sum(iff(is_brand, total_30day_fills, 0)) as brand_fills,
        sum(iff(is_brand, total_drug_cost, 0)) as brand_cost,
        sum(iff(not is_brand, total_30day_fills, 0)) as generic_fills,
        sum(iff(not is_brand, total_drug_cost, 0)) as generic_cost
    from {{ ref('int_prescriber_drug') }}
    group by generic_name, data_year
)

select
    generic_name,
    drug_class,
    data_year,
    brand_fills,
    brand_cost,
    generic_fills,
    generic_cost,
    brand_cost / nullif(brand_fills, 0) as brand_cost_per_fill,
    generic_cost / nullif(generic_fills, 0) as generic_cost_per_fill,
    greatest(brand_cost - brand_fills * (generic_cost / nullif(generic_fills, 0)), 0) as savings_upper_bound,
    brand_fills / nullif(brand_fills + generic_fills, 0) as brand_share_of_fills
from by_type
where brand_fills > 0 and generic_fills >= 100
