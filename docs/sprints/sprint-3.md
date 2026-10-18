# Sprint 3 retro: BI

Dates: 2026-10-18. Milestone: [Sprint 3 - BI](https://github.com/Tajaddin/medicare-rx-analytics/milestone/3).

**Goal:** a Power BI project (TMDL + PBIR) and Tableau Hyper extracts built from the marts, checked rather than
eyeballed. **Met.**

## Delivered

| Issue | Points | Result |
|---|---|---|
| #8 Power BI | 5 | PBIP generated from the mart schemas: 8 tables, 13 measures, 3 pages; validated against Microsoft's schemas; opened and refreshed in Power BI Desktop 2.159 |
| #9 Tableau | 3 | one `.hyper` file with the six marts, read back and compared with the marts on every run |

8 of 8 points done.

## Measured

- On the full 2022-2024 marts the extract reads back with equal row counts and column sums for all six tables
  (`reports/exports.json`, committed with the Sprint 4 run).
- 22 Power BI JSON files pass their schemas; a deliberately broken page and visual both fail, so the check is real.

## What went well

- Tests caught two bugs that would have shipped quietly: Hyper refuses `SUM` over a boolean column (the
  read-back crashed on the drug dimension), and the Snowflake connector returns `NUMBER(p, s)` as `Decimal`, which
  pandas keeps as objects, so prices would have become **text** columns in Tableau. Types now come from
  Snowflake's column metadata.

## What did not

- The schemas could not catch a model error: Power BI Desktop refused to load the project because a measure was
  named "Claims" next to a column `claims` (names are case-insensitive). The generator now refuses such clashes.
- Looking at the refreshed report found a DAX bug: "cost growth" showed **195%** because it divided the
  three-year total by one year. The measure now compares the latest year with the one before it (**7.9%**, which
  matches `reports/findings.json`).
- Ratio columns (cost per claim, shares) defaulted to SUM in visuals; they no longer aggregate.
- Hyper writes `hyperd.log` into the working directory and once failed when that directory changed under it; the
  log now goes next to the extract.

## Carried into Sprint 4

- Publishing to Tableau Public and the Power BI service needs accounts (#13).
