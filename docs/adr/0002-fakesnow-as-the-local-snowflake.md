# 0002. fakesnow as the local and CI stand-in for Snowflake

Date: 2026-10-18. Status: accepted (spike #4).

## Context

There is no Snowflake account yet (a trial needs a sign-up only the account owner can do), and CI must not need one
either. The question for the spike: can the same loader and the same dbt project run, unchanged, against
something local?

## Decision

- Use [fakesnow](https://github.com/tekumara/fakesnow) 0.11.22 in server mode: the real Snowflake Python
  connector and dbt-snowflake talk to it over HTTP, and DuckDB executes the translated SQL.
- The spike answered yes: `PUT`, plain `COPY INTO`, VARIANT path access, `try_to_decimal`, `qualify`,
  `iff`, `any_value` and dbt's table/view materialisations all work. Two things do not, and the code avoids
  them: `COPY` with a transform and `REMOVE` from a stage (ADR 0001).
- Tests start an in-process server per session; CI and `make demo` run the full pipeline on a committed sample
  of real CMS pages; a full local run uses the same server on port 8085.

## Consequences

- Every CI run exercises the real connector, dbt-snowflake and the real SQL, with no credentials.
- Emulator timings say nothing about Snowflake's. The trial-account run (#12) is the only way to get those.
