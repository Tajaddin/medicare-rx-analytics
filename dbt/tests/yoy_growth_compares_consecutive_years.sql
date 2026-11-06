-- cost_growth_yoy compares a year with the calendar year before. After a year without Florida claims it is empty:
-- growth over two years must not pass for one (the CI sample has two such generics, lovastatin among them).
select t.generic_name, t.drug_class, t.data_year, t.cost_growth_yoy, p.drug_cost as cost_year_before
from {{ ref('mart_drug_spend_trend') }} as t
left join {{ ref('mart_drug_spend_trend') }} as p
    on t.generic_name = p.generic_name and t.drug_class = p.drug_class and p.data_year = t.data_year - 1
where (p.data_year is null and t.cost_growth_yoy is not null)
   or (p.drug_cost <> 0
       and (t.cost_growth_yoy is null or abs(t.cost_growth_yoy - (t.drug_cost / p.drug_cost - 1)) > 1e-9))
