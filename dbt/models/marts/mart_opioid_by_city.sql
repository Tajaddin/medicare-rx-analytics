-- Opioid analgesic and opioid-use-disorder treatment prescribing by city and year (cities with at least 20
-- prescribers, so no row describes a handful of clinicians). OUD treatment means buprenorphine products for OUD;
-- naltrexone is left out because its prescriptions do not say whether they treat alcohol or opioid use.
with city as (
    select
        city,
        data_year,
        count(distinct npi) as prescribers,
        sum(total_claims) as all_claims,
        sum(iff(drug_class = 'opioid_analgesic', total_claims, 0)) as opioid_claims,
        sum(iff(drug_class = 'opioid_analgesic', total_day_supply, 0)) as opioid_day_supply,
        sum(iff(drug_class = 'opioid_use_disorder', total_claims, 0)) as oud_treatment_claims,
        count(distinct iff(drug_class = 'opioid_analgesic', npi, null)) as opioid_prescribers
    from {{ ref('int_prescriber_drug') }}
    group by city, data_year
)

select
    *,
    opioid_claims / nullif(all_claims, 0) as opioid_share_of_claims,
    oud_treatment_claims / nullif(opioid_claims, 0) as oud_treatment_per_opioid_claim,
    opioid_day_supply / nullif(opioid_claims, 0) as avg_opioid_days_per_claim
from city
where prescribers >= 20
