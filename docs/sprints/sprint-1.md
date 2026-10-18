# Sprint 1 retro: ingestion

Dates: 2026-10-18. Milestone: [Sprint 1 - Ingestion](https://github.com/Tajaddin/medicare-rx-analytics/milestone/1).

**Goal:** Florida Part D prescribing (2022-2024) and national drug spending land in Snowflake as raw JSON, by
tested Bash automation that resumes and verifies. **Met** (on the local emulator; no Snowflake account yet).

## Delivered

| Issue | Points | Result |
|---|---|---|
| #1 scaffold and CI | 2 | uv project, settings from the environment with validation, JSON logs, ruff/mypy/pytest/bats in CI, gitleaks and pip-audit |
| #2 Bash extractor | 5 | paged, resumable, retried, verified against the API's own row count; 6 bats tests against a fake API |
| #3 raw load | 5 | PUT, COPY INTO a landing table, one transaction per year (idempotent), lineage columns; tests against an in-process emulator |
| #4 spike | 2 | yes: the connector and dbt-snowflake run unchanged on fakesnow ([ADR 0002](../adr/0002-fakesnow-as-the-local-snowflake.md)) |

14 of 14 committed points done.

## Measured

- Extraction of all four dataset-years from data.cms.gov: **5,869,525 Florida rows and 14,536 national rows,
  1,179 pages, 3.2 GB, in 25 min 15 s with no retries**; every manifest's row count equals the API's
  (`reports/extract/`).
- The CI sample: real records of 25 Tampa prescribers (picked by a hash of the NPI) plus single rows of
  reviewed edge-case products, 2.2 MB, prescriber names removed.

## What went well

- Verifying counts at both ends (API vs pages on disk, pages copied vs rows in raw) means a partial extract or a
  half-applied load cannot pass silently.

## What did not

- `rx load --year 2024` failed on its first real use: Typer had made `year` a positional argument. Fixed, and the
  CLI tests now invoke the commands with real options.
- `PUT file://...` broke on the repository path, which contains a space. The URI is now quoted, a path with a
  quote is refused, and a test loads pages from a folder with a space.
- The dataset name went into SQL unchecked; it is now an enum in the CLI and validated in the loader, and the
  database and warehouse names must be plain identifiers.

## Carried into Sprint 2

- Nothing open. Snowflake itself (#12) waits for an account.
