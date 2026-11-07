-- A non-blank CMS number that the staging models cannot parse is a format change upstream, not a missing value:
-- staging would turn it into NULL. Every number staging reads is checked, with the type staging gives it
-- (none: integer, otherwise decimal places). One row per field: how many values fail, and one of them.
{%- set numbers = {
    'partd_prescriber_drug': [
        ('Tot_Clms', none), ('Tot_30day_Fills', 1), ('Tot_Day_Suply', none), ('Tot_Drug_Cst', 2),
        ('Tot_Benes', none), ('GE65_Tot_Clms', none), ('GE65_Tot_Drug_Cst', 2),
    ],
    'partd_spending_by_drug': [('Tot_Mftr', none)],
} %}
{%- for y in var('spending_years') %}
    {%- do numbers['partd_spending_by_drug'].extend([
        ('Tot_Spndng_' ~ y, 2), ('Tot_Dsg_Unts_' ~ y, 3), ('Tot_Clms_' ~ y, none), ('Tot_Benes_' ~ y, none),
        ('Avg_Spnd_Per_Dsg_Unt_Wghtd_' ~ y, 6), ('Avg_Spnd_Per_Clm_' ~ y, 4),
    ]) %}
{%- endfor %}

with
{%- for table, fields in numbers.items() %}
checked_{{ table }} as (
    select
    {%- for field, scale in fields %}
        {%- set path = 'record:' ~ field %}
        {%- set fails %}
            nullif(trim({{ path }}::string), '') is not null
            and {{ cms_int(path) if scale is none else cms_number(path, scale) }} is null
        {%- endset %}
        count_if({{ fails }}) as n_{{ field }},
        max(iff({{ fails }}, {{ path }}::string, null)) as example_{{ field }}{{ ',' if not loop.last }}
    {%- endfor %}
    from {{ source('raw', table) }}
){{ ',' if not loop.last }}
{%- endfor %}

{%- for table, fields in numbers.items() %}
    {%- set last_table = loop.last %}
    {%- for field, scale in fields %}
select '{{ table }}' as raw_table, '{{ field }}' as field, n_{{ field }} as unparsed, example_{{ field }} as example
from checked_{{ table }}
where n_{{ field }} > 0
        {%- if not (last_table and loop.last) %}
union all
        {%- endif %}
    {%- endfor %}
{%- endfor %}
