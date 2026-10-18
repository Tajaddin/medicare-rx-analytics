-- Therapeutic class per product (brand x generic name), from the ordered rules in seeds/drug_classes.csv.
-- The lowest priority number wins, so exceptions (apomorphine is not an opioid, insulin syringes are supplies,
-- Belbuca and Butrans are pain products while Sublocade treats OUD) are rules that sit above the broad patterns.
-- Ties go to the more specific rule. Products no rule matches are class 'other'.
with products as (
    select distinct brand_name, generic_name from {{ ref('stg_prescriber_drug') }}
    union
    select distinct brand_name, generic_name from {{ ref('stg_spending_by_drug') }}
),

matches as (
    select
        p.brand_name,
        p.generic_name,
        r.drug_class,
        row_number() over (
            partition by p.brand_name, p.generic_name
            order by r.priority, length(r.generic_pattern) + length(r.brand_pattern) desc, r.drug_class
        ) as rn
    from products as p
    inner join {{ ref('drug_classes') }} as r
        on lower(p.generic_name) like r.generic_pattern
        and lower(p.brand_name) like r.brand_pattern
)

select brand_name, generic_name, drug_class
from matches
where rn = 1
