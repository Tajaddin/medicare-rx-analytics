-- Prescribing by specialty and therapeutic class: volume, cost and the class's share of the specialty's claims.
with base as (
    select
        prescriber_type,
        drug_class,
        data_year,
        sum(total_claims) as claims,
        sum(total_drug_cost) as drug_cost,
        count(distinct npi) as prescribers
    from {{ ref('int_prescriber_drug') }}
    group by prescriber_type, drug_class, data_year
)

select
    *,
    claims / nullif(sum(claims) over (partition by prescriber_type, data_year), 0) as share_of_specialty_claims,
    drug_cost / nullif(claims, 0) as cost_per_claim
from base
