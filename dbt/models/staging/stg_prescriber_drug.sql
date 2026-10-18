-- Typed prescriber x drug x year records. Prescriber names are dropped here on purpose: every downstream
-- model works by NPI, specialty and city, and the BI layer never shows individuals.
with source as (
    select record, data_year, loaded_at from {{ source('raw', 'partd_prescriber_drug') }}
)

select
    record:Prscrbr_NPI::string                         as npi,
    initcap(trim(record:Prscrbr_City::string))         as city,
    record:Prscrbr_State_Abrvtn::string                as state,
    trim(record:Prscrbr_Type::string)                  as prescriber_type,
    trim(record:Brnd_Name::string)                     as brand_name,
    trim(record:Gnrc_Name::string)                     as generic_name,
    {{ cms_int('record:Tot_Clms') }}                    as total_claims,
    {{ cms_number('record:Tot_30day_Fills', 1) }}       as total_30day_fills,
    {{ cms_int('record:Tot_Day_Suply') }}               as total_day_supply,
    {{ cms_number('record:Tot_Drug_Cst', 2) }}          as total_drug_cost,
    -- Blank when fewer than {{ var('cms_suppression_threshold') }} beneficiaries (CMS small-cell suppression).
    {{ cms_int('record:Tot_Benes') }}                   as total_beneficiaries,
    {{ cms_int('record:GE65_Tot_Clms') }}               as claims_65_plus,
    {{ cms_number('record:GE65_Tot_Drug_Cst', 2) }}     as drug_cost_65_plus,
    nullif(trim(record:GE65_Sprsn_Flag::string), '')   as suppression_flag_65_plus,
    data_year::number(4)                               as data_year,
    loaded_at
from source
