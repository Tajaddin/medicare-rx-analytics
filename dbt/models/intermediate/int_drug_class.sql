-- Therapeutic class per generic name, from the curated pattern list in seeds/drug_classes.csv.
-- A generic name matching more than one class keeps the first by class name (the seed avoids overlaps).
with generics as (
    select distinct generic_name from {{ ref('stg_prescriber_drug') }}
    union
    select distinct generic_name from {{ ref('stg_spending_by_drug') }}
),

matches as (
    select
        g.generic_name,
        c.drug_class,
        row_number() over (partition by g.generic_name order by c.drug_class) as rn
    from generics as g
    inner join {{ ref('drug_classes') }} as c
        on lower(g.generic_name) like '%' || c.generic_name_pattern || '%'
)

select generic_name, drug_class
from matches
where rn = 1
