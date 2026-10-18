-- Prescriber x drug x year with the drug class and whether the product is a brand.
-- CMS lists a generic product with its generic name as the brand name; anything else is a branded product.
select
    p.*,
    coalesce(c.drug_class, 'other') as drug_class,
    upper(p.brand_name) <> upper(p.generic_name) as is_brand,
    p.total_drug_cost / nullif(p.total_claims, 0) as cost_per_claim,
    p.total_drug_cost / nullif(p.total_30day_fills, 0) as cost_per_30day_fill
from {{ ref('stg_prescriber_drug') }} as p
left join {{ ref('int_drug_class') }} as c using (brand_name, generic_name)
