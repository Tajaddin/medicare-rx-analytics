# 0001. Land the CMS JSON as VARIANT; type it in dbt

Date: 2026-10-18. Status: accepted.

## Context

The CMS data API returns every value as a string ("11", "288.45", "" for a suppressed count), and CMS adds or
renames columns between releases (the Part D spending file gains five columns every year). A typed raw table
would break, or silently drop data, on the first change upstream.

## Decision

- Raw tables hold one `VARIANT` record per API row plus `data_year`, `source_file` and `loaded_at`. The loader
  does nothing but land pages: `PUT` to an internal stage, `COPY INTO` a transient landing table, then one
  transaction that deletes the year and inserts it again, so a reload is idempotent.
- All typing happens in the staging models with `try_to_decimal` / `try_to_number` behind two macros, and a
  singular test fails when a non-blank value does not parse. A blank stays NULL (it means suppressed).
- A second test checks that every raw record of every year becomes exactly one staging row.

## Consequences

- A format change upstream surfaces as a failing test with the offending values, not as wrong totals.
- Querying VARIANT paths is slower than typed columns; the marts are tables, so only dbt pays that cost.
- The landing-table step exists because the local emulator supports neither `COPY` with a transform nor
  `REMOVE`; on Snowflake a transforming `COPY` would save one copy of the data.
