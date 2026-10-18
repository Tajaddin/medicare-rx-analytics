-- Fact table, grain: one prescriber (NPI) x brand name x generic name x year in Florida.
select
    npi,
    brand_name,
    generic_name,
    data_year,
    prescriber_type,
    city,
    drug_class,
    is_brand,
    total_claims,
    total_30day_fills,
    total_day_supply,
    total_drug_cost,
    total_beneficiaries
from {{ ref('int_prescriber_drug') }}
