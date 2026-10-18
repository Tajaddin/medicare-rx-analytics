# 0005. BI from exported marts: a generated Power BI project and a verified Tableau extract

Date: 2026-10-18. Status: accepted.

## Context

Power BI and Tableau both connect to Snowflake directly, but there is no account yet, and a reviewer should be
able to open the reports without one. BI files are also the part of an analytics repo that usually cannot be
reviewed: a .pbix is a binary, and nobody checks that a dashboard still matches the warehouse.

## Decision

- `rx export` writes each mart to Parquet (Power BI) and CSV, and all marts to one Tableau `.hyper` file with
  the Hyper API. It then reads the extract back and compares row counts and every numeric column's sum with
  the marts; a mismatch fails the run and raises `RxTableauExtractMismatch`.
- The Power BI report is a PBIP project (TMDL semantic model + PBIR report) written by
  `scripts/make_powerbi.py` from the Parquet schemas: column types, formats, relationships to Year and DrugClass
  dimensions, 13 measures, 3 pages. Text files diff in a pull request.
- Every PBIR/PBIP JSON file is validated in CI against the schema it names (Microsoft's published schemas), and
  CI regenerates the project from the sample exports and fails if it differs from the committed one.
- The project was opened and refreshed in Power BI Desktop 2.159 (October 2026); Desktop caught one error the
  schemas could not (a measure named like a column), now checked by the generator.

## Consequences

- Power Query needs an absolute folder path: `ExportsFolder` is a parameter the user sets once. On Snowflake the
  partitions would switch to `Snowflake.Databases`, with the same tables and measures.
- The Tableau workbook itself is not in the repo: Tableau Public needs an account to save to. The verified
  `.hyper` file and the sheet list in `docs/DEPLOY.md` are what the published dashboard is built from (#13).
