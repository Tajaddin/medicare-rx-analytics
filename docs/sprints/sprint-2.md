# Sprint 2 retro: dbt models

Dates: 2026-10-18. Milestone: [Sprint 2 - dbt models](https://github.com/Tajaddin/medicare-rx-analytics/milestone/2).

**Goal:** staging, intermediate and mart models with tests and documentation, green on Snowflake semantics
(the emulator locally and in CI). **Met**, after a bug the data review found.

## Delivered

| Issue | Points | Result |
|---|---|---|
| #5 staging | 3 | typed prescriber-drug rows (names dropped, blanks kept NULL); the spending file unpivoted to one row per year |
| #6 marts | 8 | fact table, drug dimension, spend trend, specialty mix, generic opportunity, opioids by city, GLP-1 growth |
| #7 data quality | 3 | grain, range and reconciliation tests, CMS formats parse, every raw record reaches staging, source freshness |
| #15 bug: drug classes | 3 | classes per product from ordered, reviewed rules; 23 pinned edge cases ([ADR 0004](../adr/0004-drug-classes-per-product-from-reviewed-rules.md)) |

17 points done (14 planned, 3 for the bug found during the sprint).

## Measured

- The final full build on the 2022-2024 data: **49 of 49 dbt nodes pass** (1 seed, 11 models, 37 tests); the
  run's numbers are in `reports/dbt-build.json` (committed with the Sprint 4 measured run).
- CI builds the same project on the committed sample on every push.

## What went well

- All tests passed on the first full build, including the reconciliation tests (mart totals equal staging
  totals, no staging row lost).

## What did not

- **Passing tests did not mean right answers.** Listing every generic name each class pattern matched showed
  apomorphine (Parkinson's) counted as an opioid, Relistor and Contrave as addiction treatment, insulin syringes,
  pen needles and pump cartridges as insulin, and codeine cough syrups as analgesics. Name patterns cannot tell
  Butrans (a pain patch) from Sublocade (an OUD injection): both are "Buprenorphine". Classes are now assigned per
  product with exceptions above broad rules, following CDC's opioid definitions, and a test pins each case.
- The first version of the new seed did not load: two patterns contain commas and were not quoted. The pinned
  test failed on that same run because the old classes were still in place, which is what it is for.

## Carried into Sprint 3

- Review the class match list after every yearly CMS release (in the runbook); new products only get the broad
  rules until then.
