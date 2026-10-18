{#- CMS sends every number as text; blanks are suppressed or missing values and must stay NULL. -#}
{% macro cms_number(path, scale=2) -%}
    try_to_decimal(nullif(trim({{ path }}::string), ''), 38, {{ scale }})
{%- endmacro %}

{% macro cms_int(path) -%}
    try_to_number(nullif(trim({{ path }}::string), ''))
{%- endmacro %}
