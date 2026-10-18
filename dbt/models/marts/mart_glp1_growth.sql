-- GLP-1 receptor agonists (incl. tirzepatide) by product, specialty and year: claims, cost and prescribers.
select
    generic_name,
    prescriber_type,
    data_year,
    sum(total_claims) as claims,
    sum(total_drug_cost) as drug_cost,
    count(distinct npi) as prescribers,
    sum(total_drug_cost) / nullif(sum(total_claims), 0) as cost_per_claim
from {{ ref('int_prescriber_drug') }}
where drug_class = 'glp1_receptor_agonist'
group by generic_name, prescriber_type, data_year
