-- Every raw record carries every field the staging models read. A field CMS renamed or dropped would otherwise
-- become a column of NULLs that looks like suppressed values. One row per field missing from some records.
{%- set fields = {
    'partd_prescriber_drug': [
        'Prscrbr_NPI', 'Prscrbr_City', 'Prscrbr_State_Abrvtn', 'Prscrbr_Type', 'Brnd_Name', 'Gnrc_Name', 'Tot_Clms',
        'Tot_30day_Fills', 'Tot_Day_Suply', 'Tot_Drug_Cst', 'Tot_Benes', 'GE65_Tot_Clms', 'GE65_Tot_Drug_Cst',
        'GE65_Sprsn_Flag',
    ],
    'partd_spending_by_drug': ['Brnd_Name', 'Gnrc_Name', 'Mftr_Name', 'Tot_Mftr'],
} %}
{%- for y in var('spending_years') %}
    {%- for name in ['Tot_Spndng_', 'Tot_Dsg_Unts_', 'Tot_Clms_', 'Tot_Benes_', 'Avg_Spnd_Per_Dsg_Unt_Wghtd_',
                     'Avg_Spnd_Per_Clm_', 'Outlier_Flag_'] %}
        {%- do fields['partd_spending_by_drug'].append(name ~ y) %}
    {%- endfor %}
{%- endfor %}

with
{%- for table, names in fields.items() %}
checked_{{ table }} as (
    select
    {%- for field in names %}
        count_if(record:{{ field }} is null) as n_{{ field }}{{ ',' if not loop.last }}
    {%- endfor %}
    from {{ source('raw', table) }}
){{ ',' if not loop.last }}
{%- endfor %}

{%- for table, names in fields.items() %}
    {%- set last_table = loop.last %}
    {%- for field in names %}
select '{{ table }}' as raw_table, '{{ field }}' as field, n_{{ field }} as records_without_it
from checked_{{ table }}
where n_{{ field }} > 0
        {%- if not (last_table and loop.last) %}
union all
        {%- endif %}
    {%- endfor %}
{%- endfor %}
