-- National Part D spending by drug, unpivoted from one wide record per drug and manufacturer to one row per
-- year. Only the "Overall" manufacturer rows are kept: they are the per-drug totals CMS publishes.
with source as (
    select record from {{ source('raw', 'partd_spending_by_drug') }}
    where trim(record:Mftr_Name::string) = 'Overall'
),

years as (
    {% for y in var('spending_years') %}
    select
        trim(record:Brnd_Name::string)                                   as brand_name,
        trim(record:Gnrc_Name::string)                                   as generic_name,
        {{ cms_int('record:Tot_Mftr') }}                                  as manufacturers,
        {{ y }}                                                          as data_year,
        {{ cms_number('record:Tot_Spndng_' ~ y, 2) }}                     as total_spending,
        {{ cms_number('record:Tot_Dsg_Unts_' ~ y, 3) }}                   as dosage_units,
        {{ cms_int('record:Tot_Clms_' ~ y) }}                             as total_claims,
        {{ cms_int('record:Tot_Benes_' ~ y) }}                            as total_beneficiaries,
        {{ cms_number('record:Avg_Spnd_Per_Dsg_Unt_Wghtd_' ~ y, 6) }}     as avg_spend_per_unit,
        {{ cms_number('record:Avg_Spnd_Per_Clm_' ~ y, 4) }}               as avg_spend_per_claim,
        (record:Outlier_Flag_{{ y }}::string = '1')                      as price_outlier
    from source
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
)

select * from years
where total_claims is not null
