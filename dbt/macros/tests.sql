{#- Generic tests written here instead of pulling in a package, so CI needs no dbt hub access. -#}

{% test unique_combination(model, columns) %}
select {{ columns | join(', ') }}, count(*) as n
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}

{% test at_least(model, column_name, minimum) %}
select {{ column_name }} from {{ model }}
where {{ column_name }} is not null and {{ column_name }} < {{ minimum }}
{% endtest %}

{% test between(model, column_name, minimum, maximum) %}
select {{ column_name }} from {{ model }}
where {{ column_name }} is not null and ({{ column_name }} < {{ minimum }} or {{ column_name }} > {{ maximum }})
{% endtest %}

{% test matches_pattern(model, column_name, pattern) %}
select {{ column_name }} from {{ model }}
where {{ column_name }} is not null and not regexp_like({{ column_name }}, '{{ pattern }}')
{% endtest %}

{% test row_count_matches(model, compare_model) %}
select a.n as model_rows, b.n as compared_rows
from (select count(*) as n from {{ model }}) as a
cross join (select count(*) as n from {{ compare_model }}) as b
where a.n <> b.n
{% endtest %}

{#- The sum of `column` in the model equals the sum of `compare_column` in another model (to the cent). -#}
{% test totals_match(model, compare_model, column, compare_column) %}
select a.total, b.total
from (select sum({{ column }}) as total from {{ model }}) as a
cross join (select sum({{ compare_column }}) as total from {{ compare_model }}) as b
where abs(coalesce(a.total, 0) - coalesce(b.total, 0)) > 0.01
{% endtest %}
